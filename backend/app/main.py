"""
main.py — FastAPI application entry point.

Endpoints:
  GET  /health        — liveness check
  POST /plan/intake   — parse and validate a trip request via the intake graph
                        (intake, retrieve, fetch). Does not draft an itinerary.
                        Returns the structured TripRequest on success or
                        422 Unprocessable Entity with a reason on failure.
"""
import logging
import json
import os
import time
from collections.abc import Iterator

from fastapi import FastAPI, Header, HTTPException
from fastapi import Request
from pydantic import BaseModel, ValidationError
from starlette.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.app.auth import Credentials, CurrentUser, current_user, login, logout, register
from backend.app.graph.build import intake_graph, planning_graph
from backend.app.graph.state import TripState
from backend.app.fake_model import create_fake_model
from backend.app.checks import trip_cost_breakdown
from backend.app.quota import (
    ModelCallLimitReached,
    UserModelCallLimitReached,
    limit_reached,
    record_user_model_call,
)
from backend.app.schemas import TripRequest
from backend.app.tools import CITY_COORDS
from backend.app.trips import (
    approve_trip,
    create_trip,
    delete_trip,
    get_trip,
    list_trips,
    parse_save_body,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Trip Planner Agent")

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def get_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS")
    if configured is None:
        return list(DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class IntakeRequest(BaseModel):
    """Raw user input submitted from the trip form."""
    user_input: dict


class IntakeResponse(BaseModel):
    """Validated and structured trip request."""
    request: dict


@app.post("/auth/register", status_code=201)
def auth_register(credentials: Credentials):
    return register(credentials)


@app.post("/auth/login")
def auth_login(credentials: Credentials):
    return login(credentials)


@app.post("/auth/logout")
def auth_logout(user: CurrentUser, authorization: str | None = Header(default=None)):
    return logout(user, authorization)


@app.get("/auth/me")
def auth_me(user: CurrentUser):
    return user


@app.post("/trips", status_code=201)
async def save_trip(request: Request, user: CurrentUser):
    body = await parse_save_body(request)
    return create_trip(user, body)


@app.post("/trips/{trip_id}/approve")
def approve_saved_trip(trip_id: int, user: CurrentUser):
    return approve_trip(user, trip_id)


@app.get("/trips")
def saved_trips(user: CurrentUser, status: str | None = None):
    return {"trips": list_trips(user, status)}


@app.get("/trips/{trip_id}")
def saved_trip(trip_id: int, user: CurrentUser):
    return get_trip(user, trip_id)


@app.delete("/trips/{trip_id}", status_code=204)
def remove_trip(trip_id: int, user: CurrentUser):
    delete_trip(user, trip_id)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Liveness check."""
    return {"status": "ok"}


@app.get("/options")
def options():
    """Return the choices used to build a trip request form."""
    return {
        "cities": ["Jaipur", "Chennai", "Goa"],
        "destinations": [
            {"name": name, "lat": coords[0], "lon": coords[1]}
            for name, coords in CITY_COORDS.items()
        ],
        "styles": ["relaxed", "packed"],
        "day_range": {"min": 1, "max": 7},
        "interest_suggestions": [
            "history", "food", "culture", "beaches", "nature", "shopping",
            "nightlife", "temples", "architecture", "markets", "relaxation",
        ],
    }


@app.post("/plan/intake", response_model=IntakeResponse, status_code=200)
def plan_intake(body: IntakeRequest):
    """
    Run the intake graph on the submitted user input.

    The intake graph stops after fetch, so this endpoint does not draft.

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
        "checks": [],
        "unresolved": [],
        "fake_model": None,
    }

    result = intake_graph.invoke(initial_state)

    if result.get("feedback"):
        # Join multiple reasons into one message
        reason = "; ".join(result["feedback"])
        raise HTTPException(status_code=422, detail=reason)

    if not result.get("request"):
        raise HTTPException(status_code=422, detail="Failed to parse trip request.")

    return IntakeResponse(request=result["request"])


_STEP_MESSAGES = {
    "intake": "Trip details validated.",
    "retrieve": "Guide passages retrieved.",
    "fetch": "Weather and cost estimates loaded.",
    "draft_itinerary": "Itinerary draft created.",
    "locate": "Stop coordinates looked up.",
    "check": "Draft checks completed.",
    "revise": "Draft revision completed.",
}


def _event(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _planning_event_stream(
    request: TripRequest,
    demo: bool = False,
    remaining_calls: int | None = None,
) -> Iterator[str]:
    fake_model = create_fake_model(request.model_dump()) if demo else None
    initial_state: TripState = {
        "user_input": request.model_dump(),
        "request": request.model_dump(),
        "passages": [],
        "live_data": {},
        "draft": None,
        "feedback": [],
        "revisions": 0,
        "checks": [],
        "unresolved": [],
        "fake_model": fake_model,
    }
    current = dict(initial_state)
    previous = time.perf_counter()
    try:
        updates = planning_graph.stream(initial_state, stream_mode="updates")
        yield from _stream_updates(updates, current, previous)
        yield _event("result", {
            "draft": current.get("draft"),
            "city_center": {
                "lat": CITY_COORDS[request.destination][0],
                "lon": CITY_COORDS[request.destination][1],
            },
            "cost_breakdown": trip_cost_breakdown(
                current.get("draft") or {},
                request.model_dump(),
                (current.get("live_data") or {}).get("costs") or {},
            ),
            "checks": current.get("checks", []),
            "revisions": current.get("revisions", 0),
            "unresolved": current.get("unresolved", []),
            "avoid": request.avoid,
            "costs_are_estimates": True,
            "demo": demo,
            "remaining_calls": remaining_calls,
        })
    except ModelCallLimitReached:
        yield _event("error", {"message": "Daily model call limit reached. Try again tomorrow."})
    except Exception:
        logger.exception("Planning stream failed")
        yield _event("error", {"message": "Planning failed. Please retry."})


def _stream_updates(updates, current: dict, previous: float) -> Iterator[str]:
    for update in updates:
        for node_name, node_update in update.items():
            current.update(node_update)
            now = time.perf_counter()
            step_name = "draft" if node_name == "draft_itinerary" else node_name
            message = _STEP_MESSAGES.get(node_name)
            if message:
                yield _event("step", {
                    "name": step_name,
                    "message": message,
                    "elapsed_seconds": round(now - previous, 3),
                })
            previous = now


@app.post("/plan")
def plan(request: dict, authorization: str | None = Header(default=None)):
    """Stream planning progress and the final checked itinerary as SSE."""
    try:
        validated_request = TripRequest.model_validate(request)
    except ValidationError as exc:
        unsupported_destination = any(
            error.get("loc") == ("destination",)
            and error.get("type") == "literal_error"
            for error in exc.errors()
        )
        if unsupported_destination:
            available = ", ".join(CITY_COORDS)
            return StreamingResponse(
                iter([_event(
                    "error",
                    {"message": f"That destination isn't available yet. Available now: {available}."},
                )]),
                media_type="text/event-stream",
            )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    demo = os.getenv("DEMO_MODE") == "1"
    remaining_calls = None
    if not demo:
        user = current_user(authorization)
        if limit_reached():
            raise HTTPException(
                status_code=429,
                detail="Daily model call limit reached. Try again tomorrow.",
            )
        try:
            remaining_calls = record_user_model_call(user["id"])
        except UserModelCallLimitReached as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
    return StreamingResponse(
        _planning_event_stream(validated_request, demo=demo, remaining_calls=remaining_calls),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
