import json
from unittest.mock import patch

from backend.app.graph.build import build_planning_graph
from backend.app.graph.nodes import revise_node


REQUEST = {
    "destination": "Jaipur", "days": 1, "budget": 1000,
    "interests": ["history"], "style": "relaxed", "start_date": None,
}
INTAKE = json.dumps(REQUEST)
COSTS = {
    "complete": True, "meal_budget": 100, "meal_mid": 100,
    "local_transport_per_day": 50, "typical_entry_fee_low": 10,
    "typical_entry_fee_high": 20, "stay_budget_per_night": 500,
    "stay_mid_per_night": 500,
}


def itinerary(cost=10):
    return json.dumps({
        "city": "Jaipur",
        "days": [{"day": 1, "date": None, "stops": [{
            "name": "Amber Fort", "area": "Amer", "time_slot": "morning",
            "duration_minutes": 120, "est_cost_inr": cost, "notes": "Guide details vary.",
            "outdoor": False, "passage_ids": [],
        }], "weather_note": None}],
        "total_est_cost_inr": 1, "assumptions": ["Estimates only."],
    })


def initial_state():
    return {
        "user_input": {"raw": "one day in Jaipur"}, "request": None,
        "passages": [], "live_data": {}, "draft": None, "feedback": [],
        "revisions": 0, "checks": [], "unresolved": [],
    }


def run_graph(model_responses):
    with patch("backend.app.graph.nodes.ask", side_effect=model_responses) as ask, \
         patch("backend.app.graph.nodes.retrieve", return_value=[]), \
         patch("backend.app.graph.nodes.get_weather", return_value={"available": True, "days": []}), \
         patch("backend.app.graph.nodes.load_costs", return_value=COSTS), \
         patch("backend.app.checks.geocode", return_value=None):
        result = build_planning_graph().invoke(initial_state())
    return result, ask


def test_plan_passes_without_revision():
    result, ask = run_graph([INTAKE, itinerary()])
    assert result["revisions"] == 0
    assert all(check["passed"] for check in result["checks"])
    assert ask.call_count == 2


def test_failure_then_passes_after_one_revision_and_prompt_has_feedback():
    prompts = []
    def answer(prompt):
        prompts.append(prompt)
        if len(prompts) == 1:
            return INTAKE
        if len(prompts) == 2:
            return itinerary(5000)
        return itinerary(10)
    with patch("backend.app.graph.nodes.ask", side_effect=answer) as ask, \
         patch("backend.app.graph.nodes.retrieve", return_value=[]), \
         patch("backend.app.graph.nodes.get_weather", return_value={"available": True, "days": []}), \
         patch("backend.app.graph.nodes.load_costs", return_value=COSTS), \
         patch("backend.app.checks.geocode", return_value=None):
        result = build_planning_graph().invoke(initial_state())
    assert result["revisions"] == 1
    assert all(check["passed"] for check in result["checks"])
    assert "exceeds per-person trip budget" in prompts[2]
    assert ask.call_count == 3


def test_never_passes_stops_after_three_revisions_with_unresolved_reasons():
    result, ask = run_graph([INTAKE, itinerary(5000), itinerary(5000), itinerary(5000), itinerary(5000)])
    assert result["revisions"] == 3
    assert ask.call_count == 5
    assert len(ask.call_args_list[1:]) == 4
    assert result["unresolved"]
    assert "exceeds per-person trip budget" in result["unresolved"][0]


def test_invalid_revision_keeps_previous_draft_and_counts_revision():
    state = {
        "request": REQUEST, "passages": [], "feedback": ["fix the cost"],
        "draft": json.loads(itinerary(5000)), "revisions": 0,
    }
    previous = state["draft"]
    with patch("backend.app.graph.nodes.ask", return_value="not JSON"):
        result = revise_node(state)
    assert result["draft"] == previous
    assert result["revisions"] == 1
    assert any("previous draft retained" in note for note in result["feedback"])


def test_invalid_initial_draft_ends_without_revision():
    result, ask = run_graph([INTAKE, "not JSON"])
    assert result["draft"] is None
    assert result["revisions"] == 0
    assert result["checks"][0]["name"] == "no draft"
    assert ask.call_count == 2
