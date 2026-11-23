"""Password hashing, sessions, and authenticated user helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from backend.app.db import connect

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SCRYPT_N = 16_384
SCRYPT_R = 8
SCRYPT_P = 1
SESSION_DAYS = 7
THROTTLE_SECONDS = 15 * 60
MAX_FAILED_ATTEMPTS = 5
_failed_attempts: dict[str, list[float]] = {}
_attempts_lock = threading.Lock()


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_RE.fullmatch(normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat()


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )
    encoded_salt = base64.urlsafe_b64encode(salt).decode("ascii")
    encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${encoded_salt}${encoded_digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, encoded_salt, encoded_digest = stored.split("$")
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
        expected = base64.urlsafe_b64decode(encoded_digest.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError, UnicodeError):
        return False
    return hmac.compare_digest(actual, expected)


def _user_response(row) -> dict:
    return {"id": row["id"], "email": row["email"], "created_at": row["created_at"]}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _trim_attempts(email: str, now: float) -> list[float]:
    attempts = [stamp for stamp in _failed_attempts.get(email, []) if now - stamp < THROTTLE_SECONDS]
    _failed_attempts[email] = attempts
    return attempts


def _check_throttle(email: str) -> None:
    with _attempts_lock:
        if len(_trim_attempts(email, time.monotonic())) >= MAX_FAILED_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")


def _record_failure(email: str) -> None:
    with _attempts_lock:
        attempts = _trim_attempts(email, time.monotonic())
        attempts.append(time.monotonic())


def _clear_failures(email: str) -> None:
    with _attempts_lock:
        _failed_attempts.pop(email, None)


def _create_session(connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    connection.execute(
        "INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (_token_hash(token), user_id, _timestamp(now), _timestamp(now + timedelta(days=SESSION_DAYS))),
    )
    connection.commit()
    return token


def register(credentials: Credentials) -> dict:
    with connect() as connection:
        try:
            cursor = connection.execute(
                "INSERT INTO users(email, password_hash, created_at) VALUES (?, ?, ?)",
                (credentials.email, _hash_password(credentials.password), _timestamp(_now())),
            )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed: users.email" not in str(exc):
                raise
            raise HTTPException(status_code=409, detail="Unable to register with those details.") from exc
        user = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return {"token": _create_session(connection, user["id"]), "user": _user_response(user)}


def login(credentials: Credentials) -> dict:
    _check_throttle(credentials.email)
    with connect() as connection:
        user = connection.execute("SELECT * FROM users WHERE email = ?", (credentials.email,)).fetchone()
        valid = user is not None and _verify_password(credentials.password, user["password_hash"])
        if not valid:
            _record_failure(credentials.email)
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        _clear_failures(credentials.email)
        return {"token": _create_session(connection, user["id"]), "user": _user_response(user)}


def current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    with connect() as connection:
        row = connection.execute(
            """
            SELECT users.id, users.email, users.created_at, sessions.expires_at
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
            """,
            (_token_hash(token),),
        ).fetchone()
        if row is None or datetime.fromisoformat(row["expires_at"]) <= _now():
            if row is not None:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
                connection.commit()
            raise HTTPException(status_code=401, detail="Authentication required.")
        return _user_response(row)


CurrentUser = Annotated[dict, Depends(current_user)]


def logout(user: CurrentUser, authorization: Annotated[str | None, Header()] = None) -> dict:
    token = authorization[7:].strip()
    with connect() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        connection.commit()
    return {"ok": True}
