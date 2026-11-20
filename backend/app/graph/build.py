"""
graph/build.py — assemble and compile the LangGraph workflows.

intake graph: used by /plan/intake. Runs intake, retrieve, and fetch.
planning graph: full trip planning, compiled separately so /plan/intake
does not run later steps.
"""
from langgraph.graph import END, StateGraph

from backend.app.graph.nodes import (
    check_node,
    draft_node,
    fetch_node,
    intake,
    retrieve_node,
    revise_node,
    unresolved_node,
)
from backend.app.graph.state import TripState

MAX_REVISIONS = 3


def _base_builder() -> StateGraph:
    """Shared prefix: intake, then retrieve, then fetch."""
    builder = StateGraph(TripState)
    builder.add_node("intake", intake)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("fetch", fetch_node)
    builder.set_entry_point("intake")
    builder.add_edge("intake", "retrieve")
    builder.add_edge("retrieve", "fetch")
    return builder


def build_intake_graph():
    """Compile the graph used by /plan/intake. Stops after fetch and does not draft."""
    builder = _base_builder()
    builder.add_edge("fetch", END)
    return builder.compile()


def build_planning_graph():
    """Compile the planning graph. Callers that plan a full trip use this graph."""
    builder = _base_builder()
    builder.add_node("draft_itinerary", draft_node)
    builder.add_node("check", check_node)
    builder.add_node("revise", revise_node)
    builder.add_node("mark_unresolved", unresolved_node)
    builder.add_edge("fetch", "draft_itinerary")
    builder.add_edge("draft_itinerary", "check")
    builder.add_conditional_edges(
        "check",
        _route_after_check,
        {"end": END, "revise": "revise", "unresolved": "mark_unresolved"},
    )
    builder.add_edge("revise", "check")
    builder.add_edge("mark_unresolved", END)
    return builder.compile()


def _route_after_check(state: TripState) -> str:
    if state.get("draft") is None:
        return "end"
    checks = state.get("checks", [])
    if all(item.get("passed") for item in checks):
        return "end"
    if int(state.get("revisions", 0)) >= MAX_REVISIONS:
        return "unresolved"
    return "revise"


def build_graph():
    """Return the intake graph for existing callers and tests."""
    return build_intake_graph()


intake_graph = build_intake_graph()
planning_graph = build_planning_graph()
graph = intake_graph
