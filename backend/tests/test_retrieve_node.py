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
    fort = {"text": "A fort", "section": "See", "source_url": "a"}
    food = {"text": "A meal", "section": "Eat", "source_url": "b"}
    with patch(
        "backend.app.graph.nodes.retrieve",
        side_effect=[[fort], [food], [fort]],
    ) as mocked:
        result = retrieve_node(state)

    assert mocked.call_args_list[0].args == ("Jaipur", "Jaipur forts food")
    assert mocked.call_args_list[0].kwargs == {"k": 8}
    assert [call.args[1] for call in mocked.call_args_list] == [
        "Jaipur forts food", "forts", "food",
    ]
    assert result["passages"] == [fort, food]


def test_retrieve_node_skips_without_request():
    state = _state(None)
    with patch("backend.app.graph.nodes.retrieve") as mocked:
        result = retrieve_node(state)

    mocked.assert_not_called()
    assert result["passages"] == []
