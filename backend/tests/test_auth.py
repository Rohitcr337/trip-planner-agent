from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app import auth
from backend.app.db import connect
from backend.app.main import app


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "auth.db"))
    auth._failed_attempts.clear()
    return TestClient(app)


def _register(client, email="person@example.com", password="correct horse"):
    return client.post("/auth/register", json={"email": email, "password": password})


def test_register_returns_token_and_safe_user(tmp_path, monkeypatch, caplog):
    client = _client(tmp_path, monkeypatch)
    password = "correct horse"
    response = _register(client, password=password)

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "person@example.com"
    assert body["token"]
    assert "password" not in response.text.lower()
    assert "password_hash" not in response.text
    assert password not in caplog.text


def test_email_is_lowercased_and_duplicate_is_generic(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    assert _register(client, email="Person@Example.COM").status_code == 201
    duplicate = _register(client, email="person@example.com")
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Unable to register with those details."


def test_weak_password_and_bad_email_are_rejected(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    assert _register(client, password="short").status_code == 422
    assert _register(client, email="not-an-email").status_code == 422


def test_login_success_failure_and_me(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _register(client)
    success = client.post("/auth/login", json={"email": "PERSON@example.com", "password": "correct horse"})
    assert success.status_code == 200
    token = success.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "person@example.com"

    failure = client.post("/auth/login", json={"email": "person@example.com", "password": "wrong password"})
    assert failure.status_code == 401
    assert failure.json()["detail"] == "Incorrect email or password"
    assert "person@example.com" not in failure.text


def test_login_throttles_after_five_failures(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    _register(client)
    body = {"email": "person@example.com", "password": "wrong password"}
    for _ in range(5):
        assert client.post("/auth/login", json=body).status_code == 401
    assert client.post("/auth/login", json=body).status_code == 429


def test_expired_session_is_unauthorized(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    token = _register(client).json()["token"]
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with connect() as connection:
        connection.execute("UPDATE sessions SET expires_at = ?", (expired,))
        connection.commit()
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_logout_invalidates_token_and_missing_token_is_unauthorized(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    token = _register(client).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.get("/auth/me").status_code == 401
