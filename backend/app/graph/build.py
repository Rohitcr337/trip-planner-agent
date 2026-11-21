"""
graph/build.py — assemble and compile the LangGraph workflows.

intake graph: used by /plan/intake. Runs intake, retrieve, and fetch.
planning graph: full trip planning, compiled separately so /plan/intake
does not run later steps.
"""
from langgraph.graph import END, StateGraph

from backend.app.graph.nodes import fetch_node, intake, retrieve_node
from backend.app.graph.state import TripState


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
    builder.add_edge("fetch", END)
    return builder.compile()


def build_graph():
    """Return the intake graph for existing callers and tests."""
    return build_intake_graph()


intake_graph = build_intake_graph()
planning_graph = build_planning_graph()
graph = intake_graph
