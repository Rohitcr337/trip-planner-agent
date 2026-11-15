"""
graph/build.py — assemble and compile the LangGraph workflow.

The graph grows with each phase:
  Phase 1: intake only
  Phase 2+: nodes added here in order.

The compiled graph is exposed as `graph` for import by other modules.
"""
from langgraph.graph import END, StateGraph

from backend.app.graph.nodes import intake, retrieve_node
from backend.app.graph.state import TripState

# ── Build ─────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Construct and compile the trip-planner workflow graph."""
    builder = StateGraph(TripState)

    builder.add_node("intake", intake)
    builder.add_node("retrieve", retrieve_node)
    builder.set_entry_point("intake")
    builder.add_edge("intake", "retrieve")
    builder.add_edge("retrieve", END)

    return builder.compile()


# Compiled graph — import this wherever you need to run the workflow.
graph = build_graph()
