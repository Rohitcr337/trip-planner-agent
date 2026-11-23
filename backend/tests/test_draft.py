import json
from unittest.mock import patch

from backend.app.graph.nodes import draft_node
from backend.app.itinerary import attach_weather, build_draft_prompt
from backend.app.itinerary import MAX_PROMPT_PASSAGE_CHARS, kind_from_section


def _state(**overrides):
    state = {
        "user_input": {},
        "request": {
            "destination": "Jaipur",
            "days": 1,
            "budget": 5000,
            "interests": ["history"],
            "style": "relaxed",
            "start_date": None,
        },
        "passages": [
            {
                "text": "Amber Fort is a historic fort.",
                "section": "See",
                "source_name": "Made-up guide",
                "source_url": "https://example.test/guide",
            }
        ],
        "live_data": {
            "weather": {
                "available": False,
                "reason": "No start date provided.",
                "days": [],
            },
            "costs": {"meal_mid": 400, "complete": True},
        },
        "draft": None,
        "feedback": [],
        "revisions": 0,
        "checks": [],
        "unresolved": [],
        "fake_model": None,
    }
    state.update(overrides)
    return state


def _draft_json(passage_ids=None):
    return json.dumps(
        {
            "city": "Jaipur",
            "days": [
                {
                    "day": 1,
                    "date": None,
                    "stops": [
                        {
                            "name": "Amber Fort",
                            "area": "Amer",
                            "time_slot": "morning",
                            "duration_minutes": 120,
                            "est_cost_inr": 500,
                            "notes": "Check current details.",
                            "outdoor": True,
                            "kind": "food",
                            "passage_ids": passage_ids if passage_ids is not None else [1],
                            "passage_text": "whole passage must not be returned",
                            "excerpt": "model output is replaced by passage evidence",
                        }
                    ],
                    "weather_note": None,
                }
            ],
            "total_est_cost_inr": 500,
            "assumptions": ["Costs are estimates."],
        }
    )


def test_draft_node_validates_and_fills_sources():
    with patch("backend.app.graph.nodes.ask", return_value=_draft_json()):
        result = draft_node(_state())

    stop = result["draft"]["days"][0]["stops"][0]
    assert stop["passage_ids"] == [1]
    assert stop["sources"] == [
        {
            "source_name": "Made-up guide",
            "source_url": "https://example.test/guide",
            "section": "See",
        }
    ]
    assert stop["unverified"] is False
    assert stop["outdoor"] is True
    assert stop["kind"] == "sight"
    assert stop["excerpt"] == "Amber Fort is a historic fort."
    assert "passage_text" not in stop


def test_invalid_passage_ids_and_empty_citations_are_unverified():
    with patch(
        "backend.app.graph.nodes.ask",
        return_value=_draft_json([0, 2, -1]),
    ):
        result = draft_node(_state())

    stop = result["draft"]["days"][0]["stops"][0]
    assert stop["passage_ids"] == []
    assert stop["sources"] == []
    assert stop["unverified"] is True


def test_no_passages_makes_every_stop_unverified():
    with patch("backend.app.graph.nodes.ask", return_value=_draft_json([1])):
        result = draft_node(_state(passages=[]))

    stop = result["draft"]["days"][0]["stops"][0]
    assert stop["passage_ids"] == []
    assert stop["unverified"] is True


def test_invalid_json_sets_feedback_without_crashing():
    with patch("backend.app.graph.nodes.ask", return_value="not json"):
        result = draft_node(_state())

    assert result["draft"] is None
    assert "Draft could not be created:" in result["feedback"][0]


def test_draft_skips_without_request():
    with patch("backend.app.graph.nodes.ask") as mocked:
        result = draft_node(_state(request=None))

    mocked.assert_not_called()
    assert result["draft"] is None


def test_prompt_contains_request_passages_costs_and_feedback():
    prompt = build_draft_prompt(
        _state(),
        feedback=["reduce the cost"],
        previous_draft={"city": "Jaipur"},
    )

    assert "budget (INR): 5000" in prompt
    assert "number of days: 1" in prompt
    assert "Cost estimates (these are estimates" in prompt
    assert "1. Amber Fort is a historic fort." in prompt
    assert "reduce the cost" in prompt
    assert "Previous draft" in prompt
    assert "true if the stop is mostly outdoors" in prompt
    assert "kind to sight, activity, food, or null" in prompt


def test_prompt_recommends_indoor_stops_on_rainy_days():
    assert "On rainy days in the forecast, prefer indoor stops." in build_draft_prompt(_state())


def _weather_draft(dates):
    return {"days": [{"day": index, "date": day, "weather": {"rainy": True}, "weather_note": "model text"} for index, day in enumerate(dates, 1)]}


def test_weather_is_matched_by_date_and_model_weather_text_is_replaced():
    weather = {"available": True, "days": [
        {"date": "2026-12-02", "temp_max_c": 31, "temp_min_c": 24, "precip_mm": 12, "rainy": True},
        {"date": "2026-12-03", "temp_max_c": 30, "temp_min_c": 23, "precip_mm": 0, "rainy": False},
    ]}
    result = attach_weather(_weather_draft(["2026-12-03", "2026-12-02"]), weather)
    assert result["days"][0]["weather"] == weather["days"][1]
    assert result["days"][0]["weather_note"] == "Dry, 23 to 30 C"
    assert result["days"][1]["weather"] == weather["days"][0]
    assert result["days"][1]["weather_note"] == "Rain likely (12 mm); indoor options preferred"


def test_weather_uses_order_when_dates_are_not_both_available():
    weather = {"available": True, "days": [
        {"date": "2026-12-02", "temp_max_c": 31, "temp_min_c": 24, "precip_mm": 0, "rainy": False},
    ]}
    result = attach_weather(_weather_draft([None]), weather)
    assert result["days"][0]["weather"]["date"] == "2026-12-02"


def test_weather_outside_forecast_window_is_not_assigned():
    weather = {"available": True, "days": [
        {"date": "2026-12-02", "temp_max_c": 31, "temp_min_c": 24, "precip_mm": 0, "rainy": False},
    ]}
    result = attach_weather(_weather_draft(["2026-12-12"]), weather)
    assert result["days"][0]["weather"] is None
    assert result["days"][0]["weather_note"] is None


def test_unavailable_weather_clears_model_supplied_forecast():
    result = attach_weather(_weather_draft(["2026-12-02"]), {"available": False, "reason": "Date is outside the forecast window.", "days": []})
    assert result["days"][0]["weather"] is None
    assert result["days"][0]["weather_note"] is None


def test_prompt_cleans_guide_text_without_changing_passages():
    state = _state(passages=[{
        "text": "1. **Chapora** &mdash; near _North Goa_.\n\nSee &nbsp; the fort.",
        "section": "Beaches",
        "source_name": "Guide",
        "source_url": "https://example.test/guide",
    }])
    prompt = build_draft_prompt(state)
    assert "1. Chapora — near North Goa. See the fort." in prompt
    assert "&mdash;" not in prompt and "&nbsp;" not in prompt
    assert "**" not in prompt and "_North Goa_" not in prompt
    assert state["passages"][0]["text"].startswith("1. **Chapora**")


def test_prompt_includes_places_to_avoid():
    state = _state()
    state["request"]["avoid"] = ["Amber Fort", "Marina Beach"]
    prompt = build_draft_prompt(state)

    assert "Do not include these places: Amber Fort, Marina Beach." in prompt


def test_prompt_reports_unavailable_weather_without_inventing_it():
    prompt = build_draft_prompt(_state())

    assert "Weather unavailable: No start date provided." in prompt
    assert "sunny" not in prompt.lower()


def test_stop_kind_maps_supported_sections_and_leaves_other_sections_unknown():
    assert kind_from_section("See") == "sight"
    assert kind_from_section("DO") == "activity"
    assert kind_from_section("Eat") == "food"
    assert kind_from_section("Drink") == "food"
    assert kind_from_section("Overview") is None


def test_prompt_drops_lowest_ranked_passages_to_respect_character_limit():
    passages = [
        {"text": f"{index}" + ("x" * 2499), "section": "See"}
        for index in range(1, 4)
    ]
    prompt = build_draft_prompt(_state(passages=passages))
    included = [f"{index}" + ("x" * 2499) in prompt for index in range(1, 4)]
    assert included == [True, True, False]
    passage_block = prompt.split("Retrieved passages:\n", 1)[1].split(
        "\n\nWeather summary:", 1
    )[0]
    text_lines = [line for line in passage_block.splitlines() if line.startswith(("1. ", "2. ", "3. "))]
    assert sum(len(line[3:]) for line in text_lines) <= MAX_PROMPT_PASSAGE_CHARS
