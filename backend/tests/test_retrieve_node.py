from unittest.mock import patch

from backend.app.graph.nodes import retrieve_node


def _state(request):
    return {
        "user_input": {},
        "request": request,
        "passages": [],
        "live_data": {},
        "draft": None,
        "feedback": [],
        "revisions": 0,
        "checks": [],
        "unresolved": [],
        "fake_model": None,
    }


def test_retrieve_node_builds_query_and_writes_passages():
    state = _state(
        {
            "destination": "Jaipur",
            "interests": ["forts", "food"],
        }
    )
    with patch(
        "backend.app.graph.nodes.retrieve",
        return_value=[{"text": "A fort", "section": "Places"}],
    ) as mocked:
        result = retrieve_node(state)

    mocked.assert_called_once_with("Jaipur", "Jaipur forts food")
    assert result["passages"] == [{"text": "A fort", "section": "Places"}]


def test_retrieve_node_skips_without_request():
    state = _state(None)
    with patch("backend.app.graph.nodes.retrieve") as mocked:
        result = retrieve_node(state)

    mocked.assert_not_called()
    assert result["passages"] == []
