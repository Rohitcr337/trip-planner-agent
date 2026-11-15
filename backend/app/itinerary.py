"""Structured itinerary models and the drafting prompt."""

from __future__ import annotations

import json
from datetime import date as Date
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.graph.state import TripState


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
    passage_ids: list[int]
    sources: list[Source] = Field(default_factory=list)
    unverified: bool = False


class Day(BaseModel):
    day: int = Field(gt=0)
    date: Date | None = None
    stops: list[Stop]
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

    passage_text = "\n".join(
        f"{index}. {passage.get('text', '')}\n"
        f"   Section: {passage.get('section', '')}"
        for index, passage in enumerate(passages, start=1)
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

Retrieved passages:
{passage_text}

Weather summary:
{weather_summary}

Cost estimates (these are estimates, not guaranteed prices):
{json.dumps(costs, ensure_ascii=False)}

Rules:
- Output JSON only and nothing else.
- Plan exactly the requested number of days.
- Every stop must list in passage_ids the numbers of the passages that support it, or [] if none do.
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
