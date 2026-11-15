"""
Tests for graph/build.py — task 1.5.

Covers:
- The compiled graph is importable and has the expected shape
- Running the graph with mocked ask() on a valid input yields {request: ...}
- Running the graph with mocked ask() on bad input yields {feedback: [...]}
- The graph does not raise on empty user_input
"""
import json
from unittest.mock import patch

import pytest

from backend.app.graph.build import build_graph
from backend.app.graph.state import TripState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_JSON = json.dumps({
    "destination": "Chennai",
    "days": 2,
    "budget": 6000,
    "interests": ["temples", "food"],
    "style": "packed",
})

BAD_JSON = json.dumps({
    "destination": "Narnia",
    "days": 2,
    "budget": 6000,
    "interests": ["magic"],
    "style": "relaxed",
})

def _initial_state(**kwargs) -> TripState:
    base: TripState = {
        "user_input": {},
        "request": None,
        "passages": [],
        "live_data": {},
        "draft": None,
        "feedback": [],
        "revisions": 0,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------

class TestGraphStructure:
    def test_graph_compiles_without_error(self):
        g = build_graph()
        assert g is not None

    def test_graph_has_intake_node(self):
        g = build_graph()
        # LangGraph 0.1.x exposes nodes via .nodes dict on the compiled graph
        assert "intake" in g.nodes
        assert "retrieve" in g.nodes

    def test_graph_has_fetch_node(self):
        g = build_graph()
        assert "fetch" in g.nodes

    def test_imported_graph_is_compiled(self):
        from backend.app.graph.build import graph
        assert graph is not None


# ---------------------------------------------------------------------------
# Execution tests
# ---------------------------------------------------------------------------

class TestGraphExecution:
    def test_valid_input_produces_request(self):
        g = build_graph()
        state = _initial_state(user_input={"raw": "2 days in Chennai, temples and food, budget 6000"})

        with patch("backend.app.graph.nodes.ask", return_value=VALID_JSON):
            result = g.invoke(state)

        assert result["request"] is not None
        assert result["request"]["destination"] == "Chennai"
        # feedback should be empty (no errors)
        assert result["feedback"] == []

    def test_bad_destination_produces_feedback(self):
        g = build_graph()
        state = _initial_state(user_input={"raw": "Take me to Narnia"})

        with patch("backend.app.graph.nodes.ask", return_value=BAD_JSON):
            result = g.invoke(state)

        assert result["feedback"] != []
        assert result["request"] is None

    def test_graph_does_not_raise_on_empty_input(self):
        g = build_graph()
        state = _initial_state()

        with patch("backend.app.graph.nodes.ask", return_value="not json at all"):
            result = g.invoke(state)   # must not raise

        assert "feedback" in result

    def test_graph_skips_retrieval_after_intake_failure(self):
        g = build_graph()
        state = _initial_state()

        with patch("backend.app.graph.nodes.ask", return_value="not json at all"):
            result = g.invoke(state)

        assert result["passages"] == []
