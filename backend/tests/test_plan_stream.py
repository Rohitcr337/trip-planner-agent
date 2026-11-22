import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import quota

client = TestClient(app)
REQUEST = {
    "destination": "Jaipur", "days": 1, "budget": 1000,
    "interests": ["history"], "style": "relaxed", "start_date": None,
}
PASSAGE = {
    "text": "Amber Fort is a historic fort.", "section": "Amber Fort",
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
        "outdoor": False, "passage_ids": [1],
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


def test_plan_streams_each_graph_step_and_final_result(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    with patch("backend.app.graph.nodes.ask", return_value=DRAFT) as ask, \
         patch("backend.app.graph.nodes.retrieve", return_value=[PASSAGE]), \
         patch("backend.app.graph.nodes.load_costs", return_value=CITY_COSTS), \
         patch("backend.app.graph.nodes.geocode", return_value=None), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        response = client.post("/plan", json=REQUEST)

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
    stop = result["draft"]["days"][0]["stops"][0]
    assert stop["lat"] is None and stop["lon"] is None
    assert result["checks"]
    assert result["revisions"] == 0
    assert result["unresolved"] == []
    assert result["costs_are_estimates"] is True
    assert result["demo"] is False
    ask.assert_called_once()


def test_plan_returns_friendly_429_when_daily_limit_is_reached(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    path = quota._quota_path()
    path.write_text(json.dumps({"count": quota.MAX_MODEL_CALLS_PER_DAY}), encoding="utf-8")
    with patch("backend.app.graph.nodes.ask") as ask:
        response = client.post("/plan", json=REQUEST)
    assert response.status_code == 429
    assert "Daily model call limit reached" in response.json()["detail"]
    ask.assert_not_called()


def test_plan_stream_hides_internal_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    with patch("backend.app.graph.nodes.ask", side_effect=RuntimeError("private transport details")), \
         patch("backend.app.graph.nodes.retrieve", return_value=[]), \
         patch("backend.app.graph.nodes.load_costs", return_value=CITY_COSTS), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")):
        response = client.post("/plan", json=REQUEST)
    events = _events(response.text)
    assert events[-1] == ("error", {"message": "Planning failed. Please retry."})
    assert "private transport details" not in response.text


def test_demo_mode_uses_passage_grounded_plan_without_api_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(quota, "CACHE_DIR", tmp_path)
    quota._quota_path().write_text(
        json.dumps({"count": quota.MAX_MODEL_CALLS_PER_DAY}), encoding="utf-8"
    )
    passages = [
        PASSAGE,
        {"text": "Local food stalls serve traditional dishes at Baga Beach.",
         "section": "Food and dining", "source_name": "Goa Guide",
         "source_url": "https://example.test/food"},
        {"text": "A quiet garden sits near the city museum.", "section": "City Garden",
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
    stops = result["draft"]["days"][0]["stops"]
    assert len(stops) == 3
    assert all(stop["sources"] for stop in stops)
    assert all(stop["passage_text"] for stop in stops)
