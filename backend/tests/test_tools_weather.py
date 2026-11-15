"""
Tests for get_weather — task 3.1.

All HTTP is mocked; no test makes a real network call.
Covers: normal response, out-of-range dates, missing start date,
network error, malformed response, and the on-disk cache.
"""
from datetime import date, timedelta
from unittest.mock import Mock, patch

import httpx
import pytest

from backend.app import tools


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "CACHE_DIR", tmp_path)


def _today_plus(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _fake_response(payload: dict) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def _forecast_payload(dates: list[str], precip: list[float]) -> dict:
    return {
        "daily": {
            "time": dates,
            "temperature_2m_max": [31.2 for _ in dates],
            "temperature_2m_min": [21.0 for _ in dates],
            "precipitation_sum": precip,
        }
    }


class TestWeatherNormal:
    def test_returns_days_from_forecast(self):
        start = _today_plus(1)
        second = (date.fromisoformat(start) + timedelta(days=1)).isoformat()
        payload = _forecast_payload([start, second], [0.0, 12.3])

        with patch("backend.app.tools.httpx.get", return_value=_fake_response(payload)) as get:
            result = tools.get_weather("Jaipur", start, 2)

        assert result["available"] is True
        assert result["reason"] is None
        assert result["days"] == [
            {"date": start, "temp_max_c": 31.2, "temp_min_c": 21.0, "precip_mm": 0.0, "rainy": False},
            {"date": second, "temp_max_c": 31.2, "temp_min_c": 21.0, "precip_mm": 12.3, "rainy": True},
        ]
        kwargs = get.call_args.kwargs
        assert kwargs["timeout"] == tools.HTTP_TIMEOUT_S
        assert kwargs["headers"]["User-Agent"] == tools.USER_AGENT

    def test_rainy_uses_threshold(self):
        day = _today_plus(1)
        payload = _forecast_payload([day], [tools.RAIN_MM_THRESHOLD])
        with patch("backend.app.tools.httpx.get", return_value=_fake_response(payload)):
            result = tools.get_weather("Goa", day, 1)
        assert result["days"][0]["rainy"] is True

    def test_successful_response_is_cached(self):
        day = _today_plus(1)
        payload = _forecast_payload([day], [0.0])
        with patch("backend.app.tools.httpx.get", return_value=_fake_response(payload)) as get:
            first = tools.get_weather("Chennai", day, 1)
            second = tools.get_weather("Chennai", day, 1)

        assert get.call_count == 1
        assert first == second


class TestWeatherOutOfRange:
    def test_far_future_date_is_unavailable(self):
        start = _today_plus(30)
        with patch("backend.app.tools.httpx.get") as get:
            result = tools.get_weather("Jaipur", start, 2)

        assert result["available"] is False
        assert result["days"] == []
        assert "outside the forecast window" in result["reason"]
        get.assert_not_called()

    def test_partially_out_of_range_is_unavailable(self):
        start = _today_plus(tools.FORECAST_MAX_DAYS - 1)
        with patch("backend.app.tools.httpx.get") as get:
            result = tools.get_weather("Goa", start, 2)

        assert result["available"] is False
        assert "outside the forecast window" in result["reason"]
        get.assert_not_called()

    def test_past_date_is_unavailable(self):
        with patch("backend.app.tools.httpx.get") as get:
            result = tools.get_weather("Chennai", _today_plus(-2), 1)

        assert result["available"] is False
        assert "outside the forecast window" in result["reason"]
        get.assert_not_called()


class TestWeatherMissingStartDate:
    def test_none_start_date_is_unavailable(self):
        with patch("backend.app.tools.httpx.get") as get:
            result = tools.get_weather("Jaipur", None, 2)

        assert result["available"] is False
        assert "start date" in result["reason"].lower()
        get.assert_not_called()

    def test_invalid_start_date_is_unavailable(self):
        with patch("backend.app.tools.httpx.get") as get:
            result = tools.get_weather("Jaipur", "next week", 2)

        assert result["available"] is False
        assert "valid ISO date" in result["reason"]
        get.assert_not_called()


class TestWeatherFailures:
    def test_network_error_is_unavailable_and_does_not_crash(self):
        with patch(
            "backend.app.tools.httpx.get",
            side_effect=httpx.ConnectError("connection refused"),
        ):
            result = tools.get_weather("Chennai", _today_plus(1), 1)

        assert result["available"] is False
        assert result["days"] == []
        assert "connection refused" in result["reason"]

    def test_malformed_response_is_unavailable(self):
        bad = Mock()
        bad.raise_for_status.return_value = None
        bad.json.return_value = {"daily": {"time": []}}
        with patch("backend.app.tools.httpx.get", return_value=bad):
            result = tools.get_weather("Goa", _today_plus(1), 1)

        assert result["available"] is False
        assert "could not be parsed" in result["reason"]

    def test_unknown_city_is_unavailable(self):
        with patch("backend.app.tools.httpx.get") as get:
            result = tools.get_weather("Mumbai", _today_plus(1), 1)

        assert result["available"] is False
        assert "Mumbai" in result["reason"]
        get.assert_not_called()
