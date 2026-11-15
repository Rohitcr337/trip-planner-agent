"""
Tests for get_distance — task 3.2.

All HTTP is mocked; no test makes a real network call.
Covers: haversine estimate, OSRM on and working, OSRM on and failing
(falls back to the estimate), zero distance, and the OSRM rate limit.
"""
import math
from unittest.mock import Mock, patch

import httpx
import pytest

from backend.app import tools

ORIGIN = (13.0, 80.0)
DESTINATION = (13.1, 80.0)


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(tools, "_last_osrm_call_s", 0.0)


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def _osrm_response(distance_m: float, duration_s: float) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "code": "Ok",
        "routes": [{"distance": distance_m, "duration": duration_s}],
    }
    return response


class TestEstimate:
    def test_estimate_for_known_coordinates(self, monkeypatch):
        monkeypatch.delenv(tools.OSRM_ENV_VAR, raising=False)
        expected_km = _haversine_km(ORIGIN, DESTINATION) * tools.ROAD_FACTOR

        with patch("backend.app.tools.httpx.get") as get:
            result = tools.get_distance(ORIGIN, DESTINATION)

        assert result["source"] == "estimate"
        assert result["km"] == pytest.approx(expected_km, abs=0.01)
        assert result["minutes"] == pytest.approx(expected_km / tools.CITY_SPEED_KMH * 60, abs=0.1)
        get.assert_not_called()

    def test_invalid_coordinates_do_not_crash(self):
        result = tools.get_distance(("x", 1), (0, 0))

        assert result["km"] == 0.0
        assert result["minutes"] == 0.0
        assert "error" in result


class TestOsrm:
    def test_osrm_working_returns_osrm_route(self, monkeypatch):
        monkeypatch.setenv(tools.OSRM_ENV_VAR, "1")
        with patch(
            "backend.app.tools.httpx.get",
            return_value=_osrm_response(5000.0, 600.0),
        ) as get, patch("backend.app.tools.time.sleep"):
            result = tools.get_distance(ORIGIN, DESTINATION)

        assert result == {"km": 5.0, "minutes": 10.0, "source": "osrm"}
        url = get.call_args.args[0]
        assert url == f"{tools.OSRM_URL}/80.0,13.0;80.0,13.1"
        assert get.call_args.kwargs["timeout"] == tools.HTTP_TIMEOUT_S
        assert get.call_args.kwargs["headers"]["User-Agent"] == tools.USER_AGENT

    def test_osrm_failure_falls_back_to_estimate(self, monkeypatch):
        monkeypatch.setenv(tools.OSRM_ENV_VAR, "1")
        expected_km = _haversine_km(ORIGIN, DESTINATION) * tools.ROAD_FACTOR

        with patch(
            "backend.app.tools.httpx.get",
            side_effect=httpx.ConnectError("osrm down"),
        ), patch("backend.app.tools.time.sleep"):
            result = tools.get_distance(ORIGIN, DESTINATION)

        assert result["source"] == "estimate"
        assert result["km"] == pytest.approx(expected_km, abs=0.01)
        assert result["minutes"] == pytest.approx(expected_km / tools.CITY_SPEED_KMH * 60, abs=0.1)

    def test_osrm_bad_payload_falls_back_to_estimate(self, monkeypatch):
        monkeypatch.setenv(tools.OSRM_ENV_VAR, "1")
        bad = Mock()
        bad.raise_for_status.return_value = None
        bad.json.return_value = {"code": "NoRoute", "routes": []}

        with patch("backend.app.tools.httpx.get", return_value=bad), patch(
            "backend.app.tools.time.sleep"
        ):
            result = tools.get_distance(ORIGIN, DESTINATION)

        assert result["source"] == "estimate"

    def test_successful_route_is_cached(self, monkeypatch):
        monkeypatch.setenv(tools.OSRM_ENV_VAR, "1")
        with patch(
            "backend.app.tools.httpx.get",
            return_value=_osrm_response(5000.0, 600.0),
        ) as get, patch("backend.app.tools.time.sleep"):
            first = tools.get_distance(ORIGIN, DESTINATION)
            second = tools.get_distance(ORIGIN, DESTINATION)

        assert get.call_count == 1
        assert first == second

    def test_at_most_one_osrm_request_per_second(self, monkeypatch):
        monkeypatch.setenv(tools.OSRM_ENV_VAR, "1")
        with patch(
            "backend.app.tools.httpx.get",
            return_value=_osrm_response(5000.0, 600.0),
        ), patch("backend.app.tools.time.sleep") as sleep:
            tools.get_distance(ORIGIN, DESTINATION)
            tools.get_distance((19.0, 72.0), (19.1, 72.0))

        assert sleep.call_count == 1
        assert 0 < sleep.call_args.args[0] <= tools.OSRM_MIN_INTERVAL_S


class TestZeroDistance:
    def test_zero_distance_returns_zero_estimate(self, monkeypatch):
        monkeypatch.setenv(tools.OSRM_ENV_VAR, "1")
        with patch("backend.app.tools.httpx.get") as get:
            result = tools.get_distance(ORIGIN, ORIGIN)

        assert result == {"km": 0.0, "minutes": 0.0, "source": "estimate"}
        get.assert_not_called()
