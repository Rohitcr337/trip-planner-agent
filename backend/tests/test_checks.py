from unittest.mock import patch

from backend.app.checks import check_budget, check_logistics, check_sources, run_checks, trip_cost_breakdown


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


def test_cost_breakdown_matches_budget_check_arithmetic():
    breakdown = trip_cost_breakdown(draft(), REQUEST, COSTS)
    assert breakdown == {
        "stops_inr": 100.0,
        "transport_meals_inr": 300.0,
        "stay_inr": 0.0,
        "estimate_inr": 400.0,
        "budget_inr": 500.0,
        "complete": True,
    }
    assert "Estimated total INR 400.00" in check_budget(draft(), REQUEST, COSTS).reason


def test_cost_breakdown_marks_unavailable_amounts_as_null():
    breakdown = trip_cost_breakdown(
        draft(), REQUEST,
        {"complete": False, "local_transport_per_day": 100, "meal_budget": 100},
    )
    assert breakdown == {
        "stops_inr": 100.0,
        "transport_meals_inr": 300.0,
        "stay_inr": None,
        "estimate_inr": None,
        "budget_inr": 500.0,
        "complete": False,
    }


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
    for text in ("stops", "transport and meals", "stay", "Day 1", "Palace", "INR 1500", "INR 1300"):
        assert text in result.reason


def test_logistics_rain_outdoor_and_weather_unavailable():
    d = draft()
    d["days"][0]["stops"][0]["outdoor"] = True
    live = {"weather": {"available": True, "days": [{"date": "2026-11-22", "rainy": True}]}}
    result = check_logistics(d, REQUEST, live)
    assert "travel times not checked" in result.reason
    assert "rainy day" in result.reason
    d["days"][0]["stops"][0]["outdoor"] = False
    assert "rainy day" not in check_logistics(d, REQUEST, live).reason
    assert "rain not checked" in check_logistics(d, REQUEST, {}).reason


def test_logistics_leg_day_and_active_limits_and_ungeocodable_stop():
    stops = [
        {"name": "A", "duration_minutes": 250, "outdoor": None, "lat": None, "lon": None},
        {"name": "B", "duration_minutes": 250, "outdoor": None, "lat": 1, "lon": 1},
        {"name": "C", "duration_minutes": 250, "outdoor": None, "lat": 1, "lon": 2},
    ]
    d = draft(stops)
    with patch("backend.app.checks.get_distance", return_value={"minutes": 75}):
        result = check_logistics(d, REQUEST, {"weather": {"available": True, "days": []}})
    assert "75 minutes" in result.reason
    assert "travel times not checked" not in result.reason
    assert "active time" in result.reason
    assert "3 stops" not in result.reason


def test_logistics_stop_count_and_no_draft():
    d = draft([{"name": str(i), "duration_minutes": 1} for i in range(4)])
    result = check_logistics(d, REQUEST, {})
    assert "4 stops" in result.reason
    assert run_checks({"draft": None}) == [{"name": "no draft", "passed": False,
                                             "reason": "No draft is available to check."}]


def test_logistics_uses_stored_coordinates_without_geocoding():
    d = draft([
        {"name": "A", "duration_minutes": 10, "lat": 1, "lon": 1},
        {"name": "B", "duration_minutes": 10, "lat": 1.1, "lon": 1.1},
    ])
    with patch("backend.app.tools.geocode", side_effect=AssertionError("must not geocode")) as geocode, \
         patch("backend.app.checks.get_distance", return_value={"minutes": 20}):
        result = check_logistics(d, REQUEST, {})
    geocode.assert_not_called()
    assert "travel times not checked" not in result.reason


def test_sources_require_source_or_unverified_and_report_count():
    d = draft([{"name": "Lost stop", "unverified": False, "sources": []}])
    result = check_sources(d)
    assert not result.passed and "Day 1, Lost stop" in result.reason
    d["days"][0]["stops"][0]["unverified"] = True
    assert check_sources(d).passed
    assert "1 unverified" in check_sources(d).reason
