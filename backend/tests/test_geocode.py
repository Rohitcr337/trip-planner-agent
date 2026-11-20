from unittest.mock import Mock, patch

from backend.app import tools


def response(payload):
    result = Mock()
    result.json.return_value = payload
    result.raise_for_status.return_value = None
    return result


def test_geocode_disabled(monkeypatch):
    monkeypatch.delenv("USE_GEOCODING", raising=False)
    with patch("backend.app.tools.httpx.get") as get:
        assert tools.geocode("Hawa Mahal", "Jaipur") is None
        get.assert_not_called()


def test_geocode_found_not_found_and_outside_radius(monkeypatch, tmp_path):
    monkeypatch.setenv("USE_GEOCODING", "1")
    monkeypatch.setattr(tools, "CACHE_DIR", tmp_path)
    with patch("backend.app.tools.time.sleep"), patch("backend.app.tools.httpx.get", side_effect=[
        response([{"lat": "26.92", "lon": "75.79"}]), response([]),
        response([{"lat": "28.0", "lon": "77.0"}]),
    ]) as get:
        assert tools.geocode("Hawa Mahal", "Jaipur") is not None
        assert tools.geocode("not a place", "Jaipur") is None
        assert tools.geocode("far place", "Jaipur") is None
        assert get.call_args.kwargs["timeout"] == 10.0
        assert "User-Agent" in get.call_args.kwargs["headers"]
        assert get.call_args.kwargs["params"]["bounded"] == 1


def test_geocode_cache_and_network_error(monkeypatch, tmp_path):
    monkeypatch.setenv("USE_GEOCODING", "1")
    monkeypatch.setattr(tools, "CACHE_DIR", tmp_path)
    with patch("backend.app.tools.time.sleep"), patch("backend.app.tools.httpx.get", return_value=response(
        [{"lat": "26.92", "lon": "75.79"}])) as get:
        first = tools.geocode("Cached place", "Jaipur")
        assert tools.geocode("Cached place", "Jaipur") == first
        assert get.call_count == 1
    with patch("backend.app.tools.time.sleep"), patch("backend.app.tools.httpx.get", side_effect=OSError("offline")):
        assert tools.geocode("Network place", "Jaipur") is None
