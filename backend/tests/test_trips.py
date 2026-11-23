from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app import auth
from backend.app.db import connect
from backend.app.main import app


REQUEST = {
    "destination": "Jaipur",
    "days": 1,
    "budget": 5000,
    "interests": ["history"],
    "style": "relaxed",
    "start_date": None,
    "avoid": [],
}
DRAFT = {
    "city": "Jaipur",
    "days": [
        {
            "day": 1,
            "date": None,
            "weather_note": None,
            "stops": [
                {
                    "name": "Amber Fort",
                    "area": "Amer",
                    "time_slot": "morning",
                    "duration_minutes": 90,
                    "est_cost_inr": 500,
                    "notes": "Check current details.",
                    "passage_ids": [],
                    "sources": [],
                    "unverified": True,
                }
            ],
        }
    ],
    "total_est_cost_inr": 500,
    "assumptions": [],
}


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "trips.db"))
    auth._failed_attempts.clear()
    return TestClient(app)


def _token(client, email):
    response = client.post("/auth/register", json={"email": email, "password": "correct horse"})
    return response.json()["token"]


def _body(**overrides):
    result = {"draft": DRAFT, "checks": [], "cost_breakdown": {"estimate_inr": 500}, "demo": True}
    result.update(overrides.pop("result", {}))
    body = {"request": REQUEST, "result": result}
    body.update(overrides)
    return body


def test_save_approve_list_and_delete_trip(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_token(client, 'one@example.com')}"}
    saved = client.post("/trips", json=_body(), headers=headers)
    assert saved.status_code == 201
    trip = saved.json()
    assert trip["title"] == "Jaipur · 1 days"
    assert trip["status"] == "draft"

    approved = client.post(f"/trips/{trip['id']}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_at"]
    assert client.get("/trips?status=approved", headers=headers).json()["trips"][0]["id"] == trip["id"]
    assert client.get(f"/trips/{trip['id']}", headers=headers).json()["draft"]["city"] == "Jaipur"
    assert client.delete(f"/trips/{trip['id']}", headers=headers).status_code == 204
    assert client.get(f"/trips/{trip['id']}", headers=headers).status_code == 404


def test_trips_are_private_to_the_owner(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    first = {"Authorization": f"Bearer {_token(client, 'one@example.com')}"}
    second = {"Authorization": f"Bearer {_token(client, 'two@example.com')}"}
    trip_id = client.post("/trips", json=_body(), headers=first).json()["id"]
    assert client.get(f"/trips/{trip_id}", headers=second).status_code == 404
    assert client.post(f"/trips/{trip_id}/approve", headers=second).status_code == 404
    assert client.delete(f"/trips/{trip_id}", headers=second).status_code == 404


def test_trip_validation_size_and_count_limits(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": f"Bearer {_token(client, 'one@example.com')}"}
    invalid = _body(result={"draft": {"city": "Jaipur"}})
    assert client.post("/trips", json=invalid, headers=headers).status_code == 422
    oversized = _body(title="x" * (200 * 1024))
    assert client.post("/trips", json=oversized, headers=headers).status_code == 413

    with connect() as connection:
        for index in range(50):
            connection.execute(
                """
                INSERT INTO trips(
                    user_id, title, request_json, draft_json, checks_json, cost_json,
                    demo, status, created_at
                ) VALUES (1, ?, ?, ?, ?, ?, 1, 'draft', ?)
                """,
                ("Trip", "{}", "{}", "[]", "{}", datetime.now(timezone.utc).isoformat()),
            )
        connection.commit()
    assert client.post("/trips", json=_body(), headers=headers).status_code == 409


def test_trip_endpoints_require_authentication(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    assert client.post("/trips", json=_body()).status_code == 401
    assert client.get("/trips").status_code == 401
    assert client.get("/trips/1").status_code == 401
    assert client.post("/trips/1/approve").status_code == 401
    assert client.delete("/trips/1").status_code == 401
