"""Structured itinerary models and the drafting prompt."""

from __future__ import annotations

import json
from datetime import date as Date
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.graph.state import TripState
from backend.app.text import clean_text

MAX_PROMPT_PASSAGE_CHARS = 6000
STOP_KINDS = {"see": "sight", "do": "activity", "eat": "food", "drink": "food"}


def kind_from_section(section: str | None) -> str | None:
    heading = clean_text(str(section or "").split(" > ")[-1]).casefold()
    return STOP_KINDS.get(heading)


class Source(BaseModel):
    source_name: str
    source_url: str
    section: str


class Stop(BaseModel):
    name: str
    area: str
    time_slot: Literal["morning", "afternoon", "evening"]
    duration_minutes: int = Field(gt=0)
    est_cost_inr: float = Field(ge=0)
    notes: str
    outdoor: bool | None = None
    lat: float | None = None
    lon: float | None = None
    passage_ids: list[int]
    excerpt: str = ""
    kind: Literal["sight", "activity", "food"] | None = None
    sources: list[Source] = Field(default_factory=list)
    unverified: bool = False


class DailyWeather(BaseModel):
    date: Date
    temp_max_c: float
    temp_min_c: float
    precip_mm: float
    rainy: bool


class Day(BaseModel):
    day: int = Field(gt=0)
    date: Date | None = None
    stops: list[Stop]
    weather: DailyWeather | None = None
    weather_note: str | None = None


class Itinerary(BaseModel):
    city: str
    days: list[Day]
    total_est_cost_inr: float = Field(ge=0)
    assumptions: list[str]


def build_draft_prompt(
    state: TripState,
    feedback: list[str] | None = None,
    previous_draft: dict[str, Any] | None = None,
) -> str:
    request = state.get("request") or {}
    passages = state.get("passages") or []
    live_data = state.get("live_data") or {}
    weather = live_data.get("weather")
    costs = live_data.get("costs", {})

    selected_passages = [
        (passage, clean_text(passage.get("text", ""))) for passage in passages
    ]
    while sum(len(text) for _, text in selected_passages) > MAX_PROMPT_PASSAGE_CHARS:
        selected_passages.pop()
    passage_text = "\n".join(
        f"{index}. {text}\n   Section: {passage.get('section', '')}"
        for index, (passage, text) in enumerate(selected_passages, start=1)
    ) or "(No retrieved passages.)"

    if weather and weather.get("available"):
        weather_summary = json.dumps(weather, ensure_ascii=False)
    else:
        reason = (weather or {}).get("reason", "No weather data is available.")
        weather_summary = f"Weather unavailable: {reason}"

    prompt = f"""Create a travel itinerary as JSON only and nothing else.

Request:
- destination: {request.get("destination")}
- number of days: {request.get("days")}
- budget (INR): {request.get("budget")}
- interests: {json.dumps(request.get("interests", []), ensure_ascii=False)}
- style: {request.get("style")}
- start date: {request.get("start_date") or "not provided"}
- avoid: {json.dumps(request.get("avoid", []), ensure_ascii=False)}

Retrieved passages:
{passage_text}

Weather summary:
{weather_summary}

Cost estimates (these are estimates, not guaranteed prices):
{json.dumps(costs, ensure_ascii=False)}

Rules:
- Output JSON only and nothing else.
- Do not include these places: {", ".join(request.get("avoid", [])) if request.get("avoid") else "none"}.
- Plan exactly the requested number of days.
- Every stop must list in passage_ids the numbers of the passages that support it, or [] if none do.
- For each stop, set kind to sight, activity, food, or null, based on the section of its cited passage.
- Do not include passage_text or copy full passages into a stop; include only a short excerpt when useful.
- For each stop, set outdoor to true if the stop is mostly outdoors, otherwise false; use null if unknown.
- On rainy days in the forecast, prefer indoor stops.
- Do not invent facts, prices, or opening hours; put uncertainty in notes.
- Keep each day's stops in a sensible geographic order using area for the neighbourhood or district.
- Fit the budget using the cost estimates and say so in assumptions.
- For relaxed style use at most 3 stops a day; for packed style use at most 5.
"""

    if feedback or previous_draft is not None:
        prompt += "\nRevision request:\n"
        prompt += "Fix each listed problem and change as little else as possible.\n"
        if feedback:
            prompt += f"Feedback:\n{json.dumps(feedback, ensure_ascii=False)}\n"
        if previous_draft is not None:
            prompt += (
                "Previous draft:\n"
                f"{json.dumps(previous_draft, ensure_ascii=False)}\n"
            )
    return prompt


def attach_weather(draft: dict[str, Any] | None, weather: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a copy of a draft with fetched forecast fields attached by date or order."""
    if draft is None:
        return None
    result = dict(draft)
    forecast_days = (weather or {}).get("days") or []
    available = bool((weather or {}).get("available"))
    days = []
    for index, day in enumerate(draft.get("days", [])):
        updated_day = dict(day)
        forecast = None
        if available:
            planned_date = day.get("date")
            if planned_date and any(item.get("date") for item in forecast_days):
                forecast = next(
                    (item for item in forecast_days if item.get("date") == str(planned_date)),
                    None,
                )
            elif index < len(forecast_days):
                forecast = forecast_days[index]
        updated_day["weather"] = forecast
        updated_day["weather_note"] = _weather_note(forecast) if forecast else None
        days.append(updated_day)
    result["days"] = days
    return result


def _weather_note(weather: dict[str, Any]) -> str:
    precip = weather["precip_mm"]
    if weather["rainy"]:
        return f"Rain likely ({precip:g} mm); indoor options preferred"
    low = weather["temp_min_c"]
    high = weather["temp_max_c"]
    return f"Dry, {low:g} to {high:g} C"
