import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import auth
from backend.app.main import app
from backend.app import quota

client = TestClient(app)
REQUEST = {
    "destination": "Jaipur", "days": 1, "budget": 1000,
    "interests": ["history"], "style": "relaxed", "start_date": None,
    "avoid": ["Hawa Mahal"],
}
PASSAGE = {
    "text": "- Amber Fort \u2014 a historic fort in Amer with views of the city.", "section": "See",
    "source_name": "Guide", "source_url": "https://example.test/guide",
}
CITY_COSTS = {
    "complete": True, "meal_budget": 100, "meal_mid": 100,
    "local_transport_per_day": 50, "typical_entry_fee_low": 10,
    "typical_entry_fee_high": 20, "stay_budget_per_night": 500,
    "stay_mid_per_night": 500,
}
DRAFT = json.dumps({
    "city": "Jaipur", "total_est_cost_inr": 10, "assumptions": [],
    "days": [{"day": 1, "date": None, "weather_note": None, "stops": [{
        "name": "Amber Fort", "area": "Amer", "time_slot": "morning",
        "duration_minutes": 90, "est_cost_inr": 10, "notes": "Check current details.",
        "outdoor": False, "passage_ids": [1], "passage_text": "whole passage from model",
        "excerpt": "model-supplied text",
    }]}],
})


def _events(text):
    parsed = []
    for block in text.strip().split("\n\n"):
        if not block:
            continue
        event_line, data_line = block.splitlines()
        parsed.append((event_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))))
    return parsed


def _auth_headers(tmp_path, monkeypatch, email="planner@example.com"):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "plan.db"))
    auth._failed_attempts.clear()
    token = client.post(
        "/auth/register",
        json={"email": email, "password": "correct horse"},
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_plan_streams_each_graph_step_and_final_result(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    headers = _auth_headers(tmp_path, monkeypatch)
    with patch("backend.app.graph.nodes.ask", return_value=DRAFT) as ask, \
         patch("backend.app.graph.nodes.retrieve", return_value=[PASSAGE]), \
         patch("backend.app.graph.nodes.load_costs", return_value=CITY_COSTS), \
         patch("backend.app.graph.nodes.geocode", return_value=(26.9124, 75.7873)), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        response = client.post("/plan", json=REQUEST, headers=headers)

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    events = _events(response.text)
    step_names = [payload["name"] for name, payload in events if name == "step"]
    assert step_names == ["intake", "retrieve", "fetch", "draft", "locate", "check"]
    for name, payload in events[:-1]:
        assert name == "step"
        assert isinstance(payload["elapsed_seconds"], float)
        assert payload["message"]
    event_name, result = events[-1]
    assert event_name == "result"
    assert result["draft"]["city"] == "Jaipur"
    assert result["avoid"] == ["Hawa Mahal"]
    assert result["city_center"] == {"lat": 26.9124, "lon": 75.7873}
    assert result["cost_breakdown"] == {
        "stops_inr": 10.0,
        "transport_meals_inr": 250.0,
        "stay_inr": 0.0,
        "estimate_inr": 260.0,
        "budget_inr": 1000.0,
        "complete": True,
    }
    stop = result["draft"]["days"][0]["stops"][0]
    assert stop["lat"] == 26.9124 and stop["lon"] == 75.7873
    assert stop["kind"] == "sight"
    assert "passage_text" not in stop
    assert stop["excerpt"] == "A historic fort in Amer with views of the city."
    assert result["checks"]
    assert result["revisions"] == 0
    assert result["unresolved"] == []
    assert result["costs_are_estimates"] is True
    assert result["demo"] is False
    assert result["remaining_calls"] == 4
    assert result["weather_status"] == {
        "available": False,
        "reason": "No start date provided; weather not fetched.",
    }
    assert stop.get("weather") is None
    ask.assert_called_once()


def test_plan_result_attaches_forecast_to_final_days(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    headers = _auth_headers(tmp_path, monkeypatch)
    forecast = {"available": True, "reason": None, "days": [{
        "date": "2026-12-01", "temp_max_c": 31.0, "temp_min_c": 24.0,
        "precip_mm": 12.0, "rainy": True,
    }]}
    with patch("backend.app.graph.nodes.ask", return_value=DRAFT), \
         patch("backend.app.graph.nodes.retrieve", return_value=[PASSAGE]), \
         patch("backend.app.graph.nodes.load_costs", return_value=CITY_COSTS), \
         patch("backend.app.graph.nodes.get_weather", return_value=forecast), \
         patch("backend.app.graph.nodes.geocode", return_value=None), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        response = client.post("/plan", json={**REQUEST, "start_date": "2026-12-01"}, headers=headers)

    result = _events(response.text)[-1][1]
    assert result["weather_status"] == {"available": True, "reason": ""}
    day = result["draft"]["days"][0]
    assert day["weather"] == forecast["days"][0]
    assert day["weather_note"] == "Rain likely (12 mm); indoor options preferred"
    assert day["weather_note"] != "model weather text"


def test_live_plan_requires_login(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    with patch("backend.app.graph.nodes.ask") as ask:
        response = client.post("/plan", json=REQUEST)
    assert response.status_code == 401
    ask.assert_not_called()


def test_live_plan_has_a_per_user_daily_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(quota, "PER_USER_DAILY_CALLS", 1)
    headers = _auth_headers(tmp_path, monkeypatch)
    with patch("backend.app.graph.nodes.ask", return_value=DRAFT), \
         patch("backend.app.graph.nodes.retrieve", return_value=[PASSAGE]), \
         patch("backend.app.graph.nodes.load_costs", return_value=CITY_COSTS), \
         patch("backend.app.graph.nodes.geocode", return_value=(26.9124, 75.7873)), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        first = client.post("/plan", json=REQUEST, headers=headers)
        second = client.post("/plan", json=REQUEST, headers=headers)
    assert first.status_code == 200
    assert _events(first.text)[-1][1]["remaining_calls"] == 0
    assert second.status_code == 429
    assert "Daily planning limit reached" in second.json()["detail"]


def test_daily_cap_is_counted_per_user(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(quota, "PER_USER_DAILY_CALLS", 1)
    first_headers = _auth_headers(tmp_path, monkeypatch, email="one@example.com")
    second_headers = _auth_headers(tmp_path, monkeypatch, email="two@example.com")
    with patch("backend.app.graph.nodes.ask", return_value=DRAFT), \
         patch("backend.app.graph.nodes.retrieve", return_value=[PASSAGE]), \
         patch("backend.app.graph.nodes.load_costs", return_value=CITY_COSTS), \
         patch("backend.app.graph.nodes.geocode", return_value=(26.9124, 75.7873)), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        first = client.post("/plan", json=REQUEST, headers=first_headers)
        second_user = client.post("/plan", json=REQUEST, headers=second_headers)
        blocked = client.post("/plan", json=REQUEST, headers=first_headers)
    assert first.status_code == 200
    assert second_user.status_code == 200
    assert blocked.status_code == 429


def test_plan_returns_friendly_429_when_daily_limit_is_reached(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    headers = _auth_headers(tmp_path, monkeypatch)
    path = quota._quota_path()
    path.write_text(json.dumps({"count": quota.MAX_MODEL_CALLS_PER_DAY}), encoding="utf-8")
    with patch("backend.app.graph.nodes.ask") as ask:
        response = client.post("/plan", json=REQUEST, headers=headers)
    assert response.status_code == 429
    assert "Daily model call limit reached" in response.json()["detail"]
    ask.assert_not_called()


def test_plan_streams_friendly_error_for_unsupported_destination(tmp_path, monkeypatch):
    headers = _auth_headers(tmp_path, monkeypatch)
    request = {**REQUEST, "destination": "Wakanda"}
    with patch("backend.app.graph.nodes.ask") as ask, \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        response = client.post("/plan", json=request, headers=headers)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert _events(response.text) == [(
        "error",
        {
            "code": "destination_unavailable",
            "message": "That destination isn't available yet. Available now: Jaipur, Chennai, Goa.",
            "retryable": False,
        },
    )]
    ask.assert_not_called()


def test_plan_stream_hides_internal_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    headers = _auth_headers(tmp_path, monkeypatch)
    with patch("backend.app.graph.nodes.ask", side_effect=RuntimeError("private transport details")), \
         patch("backend.app.graph.nodes.retrieve", return_value=[]), \
         patch("backend.app.graph.nodes.load_costs", return_value=CITY_COSTS), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        response = client.post("/plan", json=REQUEST, headers=headers)
    events = _events(response.text)
    assert events[-1] == ("error", {"code": "plan_failed", "message": "Planning failed. Please retry.", "retryable": True})
    assert "private transport details" not in response.text


def test_plan_stream_reports_model_unavailable(tmp_path, monkeypatch):
    from backend.app.llm import ModelUnavailableError
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    headers = _auth_headers(tmp_path, monkeypatch)
    with patch("backend.app.graph.nodes.ask", side_effect=ModelUnavailableError("upstream 503 error")), \
         patch("backend.app.graph.nodes.retrieve", return_value=[PASSAGE]), \
         patch("backend.app.graph.nodes.load_costs", return_value=CITY_COSTS), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        response = client.post("/plan", json=REQUEST, headers=headers)
    events = _events(response.text)
    assert events[-1] == ("error", {
        "code": "model_unavailable",
        "message": "The planning model is temporarily unavailable. Please retry.",
        "retryable": True,
    })
    assert "upstream 503" not in response.text


def test_plan_stream_reports_model_unavailable_when_draft_cannot_be_created(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    headers = _auth_headers(tmp_path, monkeypatch)
    with patch("backend.app.graph.nodes.ask", return_value="not valid json at all"), \
         patch("backend.app.graph.nodes.retrieve", return_value=[PASSAGE]), \
         patch("backend.app.graph.nodes.load_costs", return_value=CITY_COSTS), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        response = client.post("/plan", json=REQUEST, headers=headers)
    events = _events(response.text)
    assert events[-1] == ("error", {
        "code": "model_unavailable",
        "message": "The planning model was unable to generate an itinerary. Please retry.",
        "retryable": True,
    })


def test_plan_stream_reports_quota_reached_during_stream(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    headers = _auth_headers(tmp_path, monkeypatch)
    with patch("backend.app.graph.nodes.ask", side_effect=quota.ModelCallLimitReached), \
         patch("backend.app.graph.nodes.retrieve", return_value=[PASSAGE]), \
         patch("backend.app.graph.nodes.load_costs", return_value=CITY_COSTS), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        response = client.post("/plan", json=REQUEST, headers=headers)
    events = _events(response.text)
    assert events[-1] == ("error", {
        "code": "quota_reached",
        "message": "Daily planning limit reached. Please try again tomorrow.",
        "retryable": False,
    })


def test_plan_stream_reports_index_missing(tmp_path, monkeypatch):
    import backend.app.graph.nodes as nodes_module
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(nodes_module, "INDEX_DIR", tmp_path / "nonexistent_index")
    headers = _auth_headers(tmp_path, monkeypatch)
    with patch("backend.app.graph.nodes.load_costs", return_value=CITY_COSTS), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        response = client.post("/plan", json=REQUEST, headers=headers)
    events = _events(response.text)
    assert events[-1] == ("error", {
        "code": "index_missing",
        "message": "The travel guide index is not available. Please try again later.",
        "retryable": False,
    })


def test_no_guide_content_returns_unverified_stops_and_calm_notice(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    headers = _auth_headers(tmp_path, monkeypatch)
    with patch("backend.app.graph.nodes.ask", return_value=DRAFT), \
         patch("backend.app.graph.nodes.retrieve", return_value=[]), \
         patch("backend.app.graph.nodes.load_costs", return_value=CITY_COSTS), \
         patch("backend.app.graph.nodes.geocode", return_value=None), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        response = client.post("/plan", json=REQUEST, headers=headers)
    assert response.status_code == 200
    events = _events(response.text)
    event_name, result = events[-1]
    assert event_name == "result"
    assert result["notice"] == "Little guide material was found for this request, so suggestions are unverified"
    stops = result["draft"]["days"][0]["stops"]
    assert all(stop["unverified"] is True for stop in stops)
    assert any("unverified" in a.lower() for a in result["draft"]["assumptions"])


def test_demo_mode_uses_passage_grounded_plan_without_api_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    quota._quota_path().write_text(
        json.dumps({"count": quota.MAX_MODEL_CALLS_PER_DAY}), encoding="utf-8"
    )
    passages = [
        PASSAGE,
        {"text": "Local food stalls serve traditional dishes at Baga Beach.",
         "section": "Eat", "source_name": "Goa Guide",
         "source_url": "https://example.test/food"},
        {"text": "- City Garden — a quiet garden near the museum.", "section": "Do",
         "source_name": "Jaipur Guide", "source_url": "https://example.test/garden"},
    ]
    with patch("backend.app.graph.nodes.ask", side_effect=AssertionError("API call attempted")), \
         patch("backend.app.graph.nodes.retrieve", return_value=passages), \
         patch("backend.app.graph.nodes.load_costs", return_value=CITY_COSTS), \
         patch("backend.app.graph.nodes.geocode", return_value=None), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        response = client.post("/plan", json=REQUEST)

    assert response.status_code == 200
    events = _events(response.text)
    result = events[-1][1]
    assert events[-1][0] == "result"
    assert result["demo"] is True
    assert result["remaining_calls"] is None
    stops = result["draft"]["days"][0]["stops"]
    assert len(stops) == 3
    assert all(stop["sources"] for stop in stops)
    assert all(0 < len(stop["excerpt"]) <= 200 for stop in stops)
    assert all("passage_text" not in stop for stop in stops)
