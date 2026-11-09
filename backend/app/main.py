"""
main.py — FastAPI application entry point.

Endpoints:
  GET  /health        — liveness check
  POST /plan/intake   — parse and validate a trip request via the intake node;
                        returns the structured TripRequest on success or
                        422 Unprocessable Entity with a reason on failure.
"""
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.app.graph.nodes import intake
from backend.app.graph.state import TripState

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Trip Planner Agent")


# ── Request / Response models ─────────────────────────────────────────────────

class IntakeRequest(BaseModel):
    """Raw user input submitted from the trip form."""
    user_input: dict


class IntakeResponse(BaseModel):
    """Validated and structured trip request."""
    request: dict


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Liveness check."""
    return {"status": "ok"}


@app.post("/plan/intake", response_model=IntakeResponse, status_code=200)
def plan_intake(body: IntakeRequest):
    """
    Run the intake node on the submitted user input.

    Returns the validated TripRequest dict on success.
    Returns HTTP 422 with the validation reason(s) on failure.
    """
    initial_state: TripState = {
        "user_input": body.user_input,
        "request": None,
        "passages": [],
        "live_data": {},
        "draft": None,
        "feedback": [],
        "revisions": 0,
    }

    result = intake(initial_state)

    if "feedback" in result and result["feedback"]:
        # Join multiple reasons into one message
        reason = "; ".join(result["feedback"])
        raise HTTPException(status_code=422, detail=reason)

    return IntakeResponse(request=result["request"])
