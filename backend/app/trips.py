"""Persistence operations for user-owned trips."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError

from backend.app.auth import CurrentUser
from backend.app.db import connect
from backend.app.itinerary import Itinerary
from backend.app.schemas import TripRequest

MAX_TRIP_BODY_BYTES = 200 * 1024
MAX_TRIPS_PER_USER = 50
TRIP_STATUSES = {"draft", "approved"}


class TripResult(BaseModel):
    draft: dict[str, Any]
    checks: list[dict[str, Any]] = Field(default_factory=list)
    cost_breakdown: dict[str, Any] = Field(default_factory=dict)
    demo: bool = False


class SaveTripBody(BaseModel):
    request: TripRequest
    result: TripResult
    title: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "request": json.loads(row["request_json"]),
        "draft": json.loads(row["draft_json"]),
        "checks": json.loads(row["checks_json"]),
        "cost_breakdown": json.loads(row["cost_json"]),
        "demo": bool(row["demo"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "approved_at": row["approved_at"],
    }


def _get_owned(connection, trip_id: int, user_id: int) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM trips WHERE id = ? AND user_id = ?", (trip_id, user_id)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Trip not found.")
    return row


async def parse_save_body(request: Request) -> SaveTripBody:
    raw = await request.body()
    if len(raw) > MAX_TRIP_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Trip payload is too large.")
    try:
        body = SaveTripBody.model_validate(json.loads(raw))
        Itinerary.model_validate(body.result.draft)
        return body
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Trip request or draft is invalid.") from exc


def create_trip(user: CurrentUser, body: SaveTripBody) -> dict[str, Any]:
    title = (body.title or "").strip() or f"{body.request.destination} · {body.request.days} days"
    with connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM trips WHERE user_id = ?", (user["id"],)
        ).fetchone()["count"]
        if count >= MAX_TRIPS_PER_USER:
            raise HTTPException(status_code=409, detail="Trip limit reached.")
        cursor = connection.execute(
            """
            INSERT INTO trips(
                user_id, title, request_json, draft_json, checks_json, cost_json,
                demo, status, created_at, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, NULL)
            """,
            (
                user["id"],
                title,
                json.dumps(body.request.model_dump(mode="json"), ensure_ascii=False),
                json.dumps(body.result.draft, ensure_ascii=False),
                json.dumps(body.result.checks, ensure_ascii=False),
                json.dumps(body.result.cost_breakdown, ensure_ascii=False),
                int(body.result.demo),
                _now(),
            ),
        )
        row = connection.execute("SELECT * FROM trips WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _decode_row(row)


def list_trips(user: CurrentUser, status_filter: str | None = None) -> list[dict[str, Any]]:
    if status_filter is not None and status_filter not in TRIP_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid trip status.")
    with connect() as connection:
        if status_filter is None:
            rows = connection.execute(
                "SELECT * FROM trips WHERE user_id = ? ORDER BY created_at DESC, id DESC",
                (user["id"],),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM trips WHERE user_id = ? AND status = ? ORDER BY created_at DESC, id DESC",
                (user["id"], status_filter),
            ).fetchall()
        return [_decode_row(row) for row in rows]


def get_trip(user: CurrentUser, trip_id: int) -> dict[str, Any]:
    with connect() as connection:
        return _decode_row(_get_owned(connection, trip_id, user["id"]))


def approve_trip(user: CurrentUser, trip_id: int) -> dict[str, Any]:
    with connect() as connection:
        row = _get_owned(connection, trip_id, user["id"])
        approved_at = row["approved_at"] or _now()
        connection.execute(
            "UPDATE trips SET status = 'approved', approved_at = ? WHERE id = ?",
            (approved_at, trip_id),
        )
        connection.commit()
        return _decode_row(_get_owned(connection, trip_id, user["id"]))


def delete_trip(user: CurrentUser, trip_id: int) -> None:
    with connect() as connection:
        _get_owned(connection, trip_id, user["id"])
        connection.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        connection.commit()
