import json
from unittest.mock import patch

from backend.app.graph.nodes import draft_node
from backend.app.itinerary import build_draft_prompt
from backend.app.itinerary import MAX_PROMPT_PASSAGE_CHARS


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


def test_prompt_reports_unavailable_weather_without_inventing_it():
    prompt = build_draft_prompt(_state())

    assert "Weather unavailable: No start date provided." in prompt
    assert "sunny" not in prompt.lower()


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
