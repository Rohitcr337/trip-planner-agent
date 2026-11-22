"""Pure itinerary checks used to decide whether a draft needs revision."""
from __future__ import annotations

import logging
from typing import NamedTuple, Any

from backend.app.tools import get_distance

logger = logging.getLogger(__name__)

BUDGET_TOLERANCE = 0.0
MEALS_PER_DAY = 2
MAX_LEG_MINUTES = 60
MAX_DAY_TRAVEL_MINUTES = 180
MAX_ACTIVE_MINUTES = {"relaxed": 420, "packed": 660}
MAX_STOPS_PER_DAY = {"relaxed": 3, "packed": 5}


class CheckResult(NamedTuple):
    passed: bool
    reason: str


def _days(draft: dict) -> list[dict]:
    return draft.get("days") or []


def trip_cost_breakdown(draft: dict, request: dict, costs: dict) -> dict[str, float | bool | None]:
    """Recompute trip costs and show which parts cannot be estimated."""
    days = int(request.get("days", len(_days(draft))))
    stops = [
        (day.get("day", day_index), stop)
        for day_index, day in enumerate(_days(draft), 1)
        for stop in day.get("stops", [])
    ]
    stop_total = sum(float(stop.get("est_cost_inr") or 0) for _, stop in stops)
    budget = float(request["budget"]) if request.get("budget") is not None else None
    transport_keys = ("local_transport_per_day", "meal_budget")
    transport_meals = None
    if all(costs.get(key) is not None for key in transport_keys):
        transport_meals = days * (
            float(costs["local_transport_per_day"])
            + MEALS_PER_DAY * float(costs["meal_budget"])
        )
    stay = None
    if costs.get("stay_budget_per_night") is not None:
        stay = max(days - 1, 0) * float(costs["stay_budget_per_night"])
    estimate = stop_total + transport_meals + stay if transport_meals is not None and stay is not None else None
    complete = costs.get("complete") is not False and transport_meals is not None and stay is not None
    return {
        "stops_inr": stop_total,
        "transport_meals_inr": transport_meals,
        "stay_inr": stay,
        "estimate_inr": estimate,
        "budget_inr": budget,
        "complete": complete,
    }


def check_budget(draft: dict, request: dict, costs: dict) -> CheckResult:
    breakdown = trip_cost_breakdown(draft, request, costs)
    days = int(request.get("days", len(_days(draft))))
    stops = [
        (day.get("day", day_index), stop)
        for day_index, day in enumerate(_days(draft), 1)
        for stop in day.get("stops", [])
    ]
    missing = [
        f"Day {day_number}, {stop.get('name', 'unnamed stop')}"
        for day_number, stop in stops if stop.get("est_cost_inr") is None
    ]
    if not breakdown["complete"]:
        reason = "skipped: cost data is incomplete; budget was not checked."
        logger.warning(reason)
        return CheckResult(True, reason)
    stop_total = float(breakdown["stops_inr"])
    transport_meals = float(breakdown["transport_meals_inr"])
    stay_total = float(breakdown["stay_inr"])
    estimate = float(breakdown["estimate_inr"])
    budget = float(breakdown["budget_inr"])
    if estimate <= budget + BUDGET_TOLERANCE:
        note = f" Missing stop costs counted as 0: {', '.join(missing)}." if missing else ""
        return CheckResult(True, f"Estimated total INR {estimate:.2f} is within per-person trip budget INR {budget:.2f}.{note}")
    expensive = sorted(stops, key=lambda item: float(item[1].get("est_cost_inr") or 0), reverse=True)[:3]
    expensive_text = ", ".join(
        f"Day {day_number}, {stop.get('name', 'unnamed stop')} INR {float(stop.get('est_cost_inr') or 0):.2f}"
        for day_number, stop in expensive
    ) or "none"
    missing_text = f" Missing stop costs counted as 0: {', '.join(missing)}." if missing else ""
    return CheckResult(False, f"Estimated total INR {estimate:.2f} exceeds per-person trip budget INR {budget:.2f} by INR {estimate-budget:.2f}; breakdown: stops INR {stop_total:.2f}, transport and meals INR {transport_meals:.2f}, stay INR {stay_total:.2f}; three most expensive stops: {expensive_text}.{missing_text}")


def check_logistics(draft: dict, request: dict, live_data: dict) -> CheckResult:
    style = request.get("style", "relaxed")
    flags: list[str] = []
    notes: list[str] = []
    weather = live_data.get("weather") or {}
    weather_available = bool(weather.get("available"))
    weather_days = weather.get("days") or []
    weather_by_date = {day.get("date"): day for day in weather_days if day.get("date")}
    weather_has_dates = bool(weather_by_date)
    any_measured = False
    for day_index, day in enumerate(_days(draft), 1):
        number = day.get("day", day_index)
        stops = day.get("stops", [])
        if len(stops) > MAX_STOPS_PER_DAY.get(style, 3):
            flags.append(f"Day {number} has {len(stops)} stops; maximum for {style} style is {MAX_STOPS_PER_DAY.get(style, 3)}.")
        travel = 0.0
        active = sum(float(stop.get("duration_minutes") or 0) for stop in stops)
        prior_point = None
        prior_name = None
        for stop in stops:
            name = str(stop.get("name", "unnamed stop"))
            lat, lon = stop.get("lat"), stop.get("lon")
            point = (lat, lon) if lat is not None and lon is not None else None
            if point is None:
                prior_point = None
                prior_name = name
                continue
            if prior_point is not None:
                leg = get_distance(prior_point, point)
                minutes = leg.get("minutes") if isinstance(leg, dict) else None
                if minutes is not None:
                    any_measured = True
                    minutes = float(minutes)
                    travel += minutes
                    if minutes > MAX_LEG_MINUTES:
                        flags.append(f"Day {number}, {prior_name} to {name} takes {minutes:.0f} minutes; maximum leg is {MAX_LEG_MINUTES}.")
            prior_point, prior_name = point, name
        if travel > MAX_DAY_TRAVEL_MINUTES:
            flags.append(f"Day {number} travel totals {travel:.0f} minutes; maximum is {MAX_DAY_TRAVEL_MINUTES}.")
        active += travel
        active_limit = MAX_ACTIVE_MINUTES.get(style, MAX_ACTIVE_MINUTES["relaxed"])
        if active > active_limit:
            flags.append(f"Day {number} active time is {active:.0f} minutes; maximum for {style} style is {active_limit}.")
        if day.get("date") and weather_has_dates:
            forecast = weather_by_date.get(day.get("date"))
        elif day_index <= len(weather_days):
            forecast = weather_days[day_index - 1]
        else:
            forecast = None
        rainy = bool(forecast and forecast.get("rainy"))
        if weather_available and rainy:
            for stop in stops:
                if stop.get("outdoor") is True:
                    flags.append(f"Day {number}, {stop.get('name', 'unnamed stop')} is mostly outdoors on a rainy day.")
    if not weather_available:
        notes.append("rain not checked: weather is unavailable.")
    if not any_measured:
        notes.append("travel times not checked: no leg could be measured.")
    if flags:
        reason = " ".join(flags + notes)
    else:
        reason = "All stop counts, travel times, active times, and available weather checks passed."
        if notes:
            reason += " " + " ".join(notes)
    return CheckResult(not flags, reason)


def check_sources(draft: dict) -> CheckResult:
    unverified_count = 0
    missing = []
    for day_index, day in enumerate(_days(draft), 1):
        number = day.get("day", day_index)
        for stop in day.get("stops", []):
            sources = stop.get("sources") or []
            if stop.get("unverified"):
                unverified_count += 1
            elif not sources:
                missing.append(f"Day {number}, {stop.get('name', 'unnamed stop')}")
    prefix = f"{unverified_count} unverified stop(s)."
    if missing:
        return CheckResult(False, f"{prefix} Missing source and unverified label: {', '.join(missing)}.")
    return CheckResult(True, f"Every stop has a source or is marked unverified. {prefix}")


def run_checks(state: dict[str, Any]) -> list[dict[str, Any]]:
    draft = state.get("draft")
    if draft is None:
        return [{"name": "no draft", "passed": False, "reason": "No draft is available to check."}]
    request = state.get("request") or {}
    live_data = state.get("live_data") or {}
    costs = live_data.get("costs") or {}
    return [
        {"name": name, "passed": result.passed, "reason": result.reason}
        for name, result in (
            ("budget", check_budget(draft, request, costs)),
            ("logistics", check_logistics(draft, request, live_data)),
            ("sources", check_sources(draft)),
        )
    ]
