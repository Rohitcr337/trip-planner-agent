"""
schemas.py — Pydantic models for request validation.

TripRequest is the canonical shape of a validated trip planning request.
It is used by the intake node and the /plan/intake endpoint.
"""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TripRequest(BaseModel):
    """A validated trip planning request."""

    destination: Literal["Jaipur", "Chennai", "Goa"] = Field(
        description="Target city — one of Jaipur, Chennai, or Goa."
    )
    days: int = Field(ge=1, le=7, description="Trip duration in days (1–7).")
    budget: float = Field(gt=0, description="Total budget in INR (must be > 0).")
    interests: list[str] = Field(
        description="List of interest tags, e.g. ['food', 'history']."
    )
    style: Literal["relaxed", "packed"] = Field(
        description="Pacing preference: 'relaxed' or 'packed'."
    )
    start_date: str | None = Field(
        default=None,
        description="Optional trip start date as an ISO date (YYYY-MM-DD).",
    )
    avoid: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Place names that should not appear in the itinerary.",
    )

    @field_validator("interests")
    @classmethod
    def interests_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("interests must contain at least one item.")
        return v

    @field_validator("start_date")
    @classmethod
    def start_date_must_be_iso(cls, v: str | None) -> str | None:
        if v is None:
            return None
        try:
            return date.fromisoformat(v).isoformat()
        except (TypeError, ValueError) as exc:
            raise ValueError("start_date must be an ISO date (YYYY-MM-DD).") from exc

    @field_validator("avoid")
    @classmethod
    def avoid_entries_must_be_valid(cls, entries: list[str]) -> list[str]:
        import re

        cleaned: list[str] = []
        for entry in entries:
            if not isinstance(entry, str):
                raise ValueError("avoid entries must be strings.")
            value = re.sub(r"\s+", " ", entry.strip())
            if not value:
                raise ValueError("avoid entries cannot be empty.")
            if len(value) > 80:
                raise ValueError("avoid entries cannot exceed 80 characters.")
            cleaned.append(value)
        return cleaned

