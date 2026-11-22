from unittest.mock import patch

from backend.app.graph.nodes import locate_node


def _state():
    return {
        "request": {"destination": "Jaipur"},
        "draft": {
            "city": "Jaipur",
            "days": [{"day": 1, "stops": [
                {"name": "Amber Fort", "lat": 99, "lon": 99},
                {"name": "Unknown place", "lat": 88, "lon": 88},
            ]}],
        },
    }


def test_locate_node_writes_coordinates_and_clears_unverified_values():
    with patch("backend.app.graph.nodes.geocode", side_effect=[(26.9855, 75.8513), None]) as lookup:
        result = locate_node(_state())

    stops = result["draft"]["days"][0]["stops"]
    assert (stops[0]["lat"], stops[0]["lon"]) == (26.9855, 75.8513)
    assert stops[1]["lat"] is None and stops[1]["lon"] is None
    lookup.assert_any_call("Amber Fort", "Jaipur")
    lookup.assert_any_call("Unknown place", "Jaipur")
