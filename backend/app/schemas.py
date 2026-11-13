"""
schemas.py — Pydantic models for request validation.

TripRequest is the canonical shape of a validated trip planning request.
It is used by the intake node and the /plan/intake endpoint.
"""
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

    @field_validator("interests")
    @classmethod
    def interests_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("interests must contain at least one item.")
        return v
