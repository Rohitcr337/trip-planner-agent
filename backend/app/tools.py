"""
tools.py — live-data tools used by the agent (weather, distance).

Tools never raise on network or parsing problems: they return a result with
available=False and a human-readable reason. Successful responses are cached
on disk under cache/, keyed by the request that produced them.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Tunables ──────────────────────────────────────────────────────────────────

CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"
HTTP_TIMEOUT_S = 10.0
USER_AGENT = "TripPlannerAgent/0.3 (educational trip planner; local development)"

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
RAIN_MM_THRESHOLD = 5.0
WEATHER_CACHE_TTL_S = 6 * 60 * 60
FORECAST_MAX_DAYS = 16  # Open-Meteo forecast horizon, today included

CITY_COORDS: dict[str, tuple[float, float]] = {
    "Jaipur": (26.9124, 75.7873),
    "Chennai": (13.0827, 80.2707),
    "Goa": (15.4909, 73.8278),  # Panaji, Goa's capital and main city centre
}

EARTH_RADIUS_KM = 6371.0
ROAD_FACTOR = 1.3
CITY_SPEED_KMH = 25.0

OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
OSRM_ENV_VAR = "USE_OSRM"
OSRM_CACHE_TTL_S = 24 * 60 * 60
OSRM_MIN_INTERVAL_S = 1.0

_last_osrm_call_s = 0.0


# ── Disk cache ────────────────────────────────────────────────────────────────

def _cache_key(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _cache_read(kind: str, payload: dict[str, Any], ttl_s: float) -> Any | None:
    path = CACHE_DIR / f"{kind}_{_cache_key(payload)}.json"
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
        age_s = time.time() - float(entry["cached_at"])
        if age_s > ttl_s:
            return None
        return entry["result"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _cache_write(kind: str, payload: dict[str, Any], result: Any) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = CACHE_DIR / f"{kind}_{_cache_key(payload)}.json"
        path.write_text(
            json.dumps({"cached_at": time.time(), "result": result}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Could not write %s cache entry: %s", kind, exc)


# ── Weather ───────────────────────────────────────────────────────────────────

def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason, "days": []}


def _parse_forecast(data: Any, dates: list[date]) -> dict[str, Any]:
    """Turn an Open-Meteo daily payload into our day list, or raise ValueError."""
    if not isinstance(data, dict):
        raise ValueError("weather response is not a JSON object")
    daily = data.get("daily") or {}
    times = daily.get("time") or []
    temp_max = daily.get("temperature_2m_max") or []
    temp_min = daily.get("temperature_2m_min") or []
    precip = daily.get("precipitation_sum") or []
    if not (len(times) == len(temp_max) == len(temp_min) == len(precip)):
        raise ValueError("daily weather series are missing or misaligned")

    index = {value: i for i, value in enumerate(times)}
    days: list[dict[str, Any]] = []
    for day in dates:
        iso = day.isoformat()
        if iso not in index:
            raise ValueError(f"no forecast returned for {iso}")
        i = index[iso]
        raw = (temp_max[i], temp_min[i], precip[i])
        if any(value is None for value in raw):
            raise ValueError(f"incomplete forecast for {iso}")
        try:
            hi, lo, mm = (float(value) for value in raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"non-numeric forecast for {iso}") from exc
        days.append(
            {
                "date": iso,
                "temp_max_c": round(hi, 1),
                "temp_min_c": round(lo, 1),
                "precip_mm": round(mm, 1),
                "rainy": mm >= RAIN_MM_THRESHOLD,
            }
        )
    return {"available": True, "reason": None, "days": days}


def get_weather(city: str, start_date: str | None, days: int) -> dict[str, Any]:
    """
    Return daily weather for a supported city.

    Shape: {"available": bool, "reason": str | None, "days": [...]}
    Every failure (missing date, out-of-range date, network, parsing) is
    reported as available=False with a reason; this function never raises.
    """
    if not start_date:
        return _unavailable("No start date provided; weather cannot be fetched.")

    coords = CITY_COORDS.get(city)
    if coords is None:
        supported = ", ".join(sorted(CITY_COORDS))
        return _unavailable(f"No coordinates configured for {city!r}; supported cities: {supported}.")

    try:
        start = date.fromisoformat(str(start_date))
    except ValueError:
        return _unavailable(f"start_date is not a valid ISO date (YYYY-MM-DD): {start_date!r}")

    try:
        day_count = int(days)
    except (TypeError, ValueError):
        return _unavailable(f"days is not an integer: {days!r}")
    if day_count < 1:
        return _unavailable("days must be at least 1.")

    today = date.today()
    last_covered = today + timedelta(days=FORECAST_MAX_DAYS - 1)
    requested = [start + timedelta(days=offset) for offset in range(day_count)]
    end = requested[-1]
    if start < today or end > last_covered:
        return _unavailable(
            f"Requested dates {start.isoformat()}..{end.isoformat()} are outside the "
            f"forecast window {today.isoformat()}..{last_covered.isoformat()}."
        )

    payload = {"city": city, "start_date": start.isoformat(), "days": day_count}
    cached = _cache_read("weather", payload, WEATHER_CACHE_TTL_S)
    if cached is not None:
        return cached

    params = {
        "latitude": coords[0],
        "longitude": coords[1],
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "timezone": "auto",
    }

    try:
        response = httpx.get(
            OPEN_METEO_URL,
            params=params,
            timeout=HTTP_TIMEOUT_S,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        data = response.json()
        result = _parse_forecast(data, requested)
    except httpx.HTTPError as exc:
        return _unavailable(f"Weather service request failed: {exc}")
    except (ValueError, KeyError, TypeError) as exc:
        return _unavailable(f"Weather response could not be parsed: {exc}")

    _cache_write("weather", payload, result)
    return result

# ── Distance ──────────────────────────────────────────────────────────────────

def _haversine_km(origin: tuple[float, float], destination: tuple[float, float]) -> float:
    """Great-circle distance between two (lat, lon) points, in kilometres."""
    lat1, lon1 = map(math.radians, origin)
    lat2, lon2 = map(math.radians, destination)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def _estimate_route(origin: tuple[float, float], destination: tuple[float, float]) -> dict[str, Any]:
    straight_km = _haversine_km(origin, destination)
    road_km = straight_km * ROAD_FACTOR
    return {
        "km": round(road_km, 2),
        "minutes": round(road_km / CITY_SPEED_KMH * 60, 1),
        "source": "estimate",
    }


def _wait_for_osrm_slot() -> None:
    global _last_osrm_call_s
    wait_s = _last_osrm_call_s + OSRM_MIN_INTERVAL_S - time.monotonic()
    if wait_s > 0:
        time.sleep(wait_s)
    _last_osrm_call_s = time.monotonic()


def _parse_osrm(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("code") != "Ok":
        raise ValueError("OSRM did not return a route")
    routes = data.get("routes") or []
    if not routes:
        raise ValueError("OSRM returned no routes")
    distance_m = float(routes[0]["distance"])
    duration_s = float(routes[0]["duration"])
    return {
        "km": round(distance_m / 1000, 2),
        "minutes": round(duration_s / 60, 1),
        "source": "osrm",
    }


def _valid_point(point: Any) -> tuple[float, float]:
    lat, lon = float(point[0]), float(point[1])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"coordinates out of range: {point!r}")
    return lat, lon


def get_distance(origin: tuple[float, float], destination: tuple[float, float]) -> dict[str, Any]:
    """
    Estimate travel distance and time between two (latitude, longitude) points.

    Returns {"km": float, "minutes": float, "source": "estimate" | "osrm"}.
    The estimate is the haversine distance times ROAD_FACTOR at CITY_SPEED_KMH.
    A live OSRM call is used only when USE_OSRM=1, and any OSRM failure falls
    back to the estimate. Invalid coordinates never raise; they return zeros
    with an "error" reason.
    """
    try:
        start = _valid_point(origin)
        end = _valid_point(destination)
    except (TypeError, ValueError, IndexError, KeyError) as exc:
        return {
            "km": 0.0,
            "minutes": 0.0,
            "source": "estimate",
            "error": f"Invalid coordinates: {exc}",
        }

    estimate = _estimate_route(start, end)
    if estimate["km"] == 0.0:
        return estimate
    if os.getenv(OSRM_ENV_VAR) != "1":
        return estimate

    payload = {"origin": start, "destination": end}
    cached = _cache_read("osrm", payload, OSRM_CACHE_TTL_S)
    if cached is not None:
        return cached

    url = f"{OSRM_URL}/{start[1]},{start[0]};{end[1]},{end[0]}"
    try:
        _wait_for_osrm_slot()
        response = httpx.get(
            url,
            params={"overview": "false"},
            timeout=HTTP_TIMEOUT_S,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        result = _parse_osrm(response.json())
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        logger.warning("OSRM lookup failed, using estimate: %s", exc)
        return estimate

    _cache_write("osrm", payload, result)
    return result
