from unittest.mock import patch

from backend.app.checks import check_budget, check_logistics, check_sources, run_checks


def draft(stops=None):
    return {"city": "Jaipur", "total_est_cost_inr": 999999, "days": [
        {"day": 1, "date": "2026-11-22", "stops": stops if stops is not None else [
            {"name": "Museum", "duration_minutes": 60, "est_cost_inr": 100,
             "outdoor": False, "sources": [{"source_name": "Guide"}], "unverified": False}
        ]}
    ]}


COSTS = {"complete": True, "local_transport_per_day": 100, "meal_budget": 100,
         "stay_budget_per_night": 500}
REQUEST = {"destination": "Jaipur", "days": 1, "budget": 500, "style": "relaxed"}


def test_budget_uses_code_total_and_edges():
    d = draft()
    assert check_budget(d, REQUEST, COSTS).passed  # estimate 300; model total ignored
    assert check_budget(d, {**REQUEST, "budget": 400}, COSTS).passed
    assert check_budget(d, {**REQUEST, "budget": 401}, COSTS).passed
    assert not check_budget(d, {**REQUEST, "budget": 399.99}, COSTS).passed


def test_incomplete_costs_skip_and_missing_stop_cost_counts_zero():
    result = check_budget(draft(), REQUEST, {"complete": False})
    assert result.passed and result.reason.startswith("skipped:")
    stop = {"name": "Free museum", "duration_minutes": 20, "sources": [], "unverified": True}
    assert check_budget(draft([stop]), REQUEST, COSTS).passed
    assert "Free museum" in check_budget(draft([stop]), REQUEST, COSTS).reason


def test_budget_overage_has_breakdown_and_expensive_stops():
    d = draft([{"name": "Palace", "est_cost_inr": 1000}, {"name": "Gallery", "est_cost_inr": 500}])
    result = check_budget(d, REQUEST, COSTS)
    assert not result.passed
    for text in ("stops", "transport and meals", "stay", "Palace", "INR 1500", "INR 1300"):
        assert text in result.reason


def test_logistics_rain_outdoor_and_weather_unavailable():
    d = draft()
    d["days"][0]["stops"][0]["outdoor"] = True
    live = {"weather": {"available": True, "days": [{"date": "2026-11-22", "rainy": True}]}}
    with patch("backend.app.checks.geocode", return_value=None):
        result = check_logistics(d, REQUEST, live)
    assert "travel times not checked" in result.reason
    assert "rainy day" in result.reason
    d["days"][0]["stops"][0]["outdoor"] = False
    with patch("backend.app.checks.geocode", return_value=None):
        assert "rainy day" not in check_logistics(d, REQUEST, live).reason
        assert "rain not checked" in check_logistics(d, REQUEST, {}).reason


def test_logistics_leg_day_and_active_limits_and_ungeocodable_stop():
    stops = [{"name": name, "duration_minutes": 250, "outdoor": None} for name in "ABC"]
    d = draft(stops)
    with patch("backend.app.checks.geocode", side_effect=[None, (1, 1), (1, 2)]), \
         patch("backend.app.checks.get_distance", return_value={"minutes": 75}):
        result = check_logistics(d, REQUEST, {"weather": {"available": True, "days": []}})
    assert "75 minutes" in result.reason
    assert "travel times not checked" not in result.reason
    assert "active time" in result.reason
    assert "3 stops" not in result.reason


def test_logistics_stop_count_and_no_draft():
    d = draft([{"name": str(i), "duration_minutes": 1} for i in range(4)])
    with patch("backend.app.checks.geocode", return_value=None):
        result = check_logistics(d, REQUEST, {})
    assert "4 stops" in result.reason
    assert run_checks({"draft": None}) == [{"name": "no draft", "passed": False,
                                             "reason": "No draft is available to check."}]


def test_sources_require_source_or_unverified_and_report_count():
    d = draft([{"name": "Lost stop", "unverified": False, "sources": []}])
    result = check_sources(d)
    assert not result.passed and "Day 1, Lost stop" in result.reason
    d["days"][0]["stops"][0]["unverified"] = True
    assert check_sources(d).passed
    assert "1 unverified" in check_sources(d).reason
