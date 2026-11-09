"""
Tests for FastAPI endpoints — task 1.6.

Covers:
  GET  /health        — returns 200 {"status": "ok"}
  POST /plan/intake   — valid input → 200 with structured request
  POST /plan/intake   — missing budget → 422 with reason
  POST /plan/intake   — nonsense destination → 422 with reason
  POST /plan/intake   — completely empty user_input → 422 (does not crash)
  POST /plan/intake   — model returns non-JSON → 422 (does not crash)
"""
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

VALID_JSON = json.dumps({
    "destination": "Goa",
    "days": 4,
    "budget": 12000,
    "interests": ["beach", "nightlife"],
    "style": "packed",
})

MISSING_BUDGET_JSON = json.dumps({
    "destination": "Goa",
    "days": 4,
    "interests": ["beach"],
    "style": "packed",
    # budget omitted
})

BAD_DEST_JSON = json.dumps({
    "destination": "Wakanda",
    "days": 3,
    "budget": 5000,
    "interests": ["vibranium"],
    "style": "relaxed",
})


def _mock_ask(text: str):
    return patch("backend.app.graph.nodes.ask", return_value=text)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_body(self):
        resp = client.get("/health")
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /plan/intake — success
# ---------------------------------------------------------------------------

class TestIntakeEndpointSuccess:
    def test_valid_input_returns_200(self):
        with _mock_ask(VALID_JSON):
            resp = client.post("/plan/intake", json={"user_input": {"raw": "4 days in Goa"}})
        assert resp.status_code == 200

    def test_valid_input_returns_request(self):
        with _mock_ask(VALID_JSON):
            resp = client.post("/plan/intake", json={"user_input": {"raw": "4 days in Goa"}})
        body = resp.json()
        assert "request" in body
        req = body["request"]
        assert req["destination"] == "Goa"
        assert req["days"] == 4
        assert req["budget"] == 12000
        assert req["style"] == "packed"

    def test_valid_input_no_feedback_key(self):
        with _mock_ask(VALID_JSON):
            resp = client.post("/plan/intake", json={"user_input": {"raw": "4 days in Goa"}})
        assert "feedback" not in resp.json()


# ---------------------------------------------------------------------------
# POST /plan/intake — failures → 422
# ---------------------------------------------------------------------------

class TestIntakeEndpointFailures:
    def test_missing_budget_returns_422(self):
        with _mock_ask(MISSING_BUDGET_JSON):
            resp = client.post("/plan/intake", json={"user_input": {"raw": "Goa trip, no budget"}})
        assert resp.status_code == 422

    def test_missing_budget_has_detail(self):
        with _mock_ask(MISSING_BUDGET_JSON):
            resp = client.post("/plan/intake", json={"user_input": {"raw": "Goa trip"}})
        body = resp.json()
        assert "detail" in body

    def test_bad_destination_returns_422(self):
        with _mock_ask(BAD_DEST_JSON):
            resp = client.post("/plan/intake", json={"user_input": {"raw": "Take me to Wakanda"}})
        assert resp.status_code == 422

    def test_bad_destination_has_detail(self):
        with _mock_ask(BAD_DEST_JSON):
            resp = client.post("/plan/intake", json={"user_input": {"raw": "Wakanda trip"}})
        body = resp.json()
        assert "detail" in body
        assert len(body["detail"]) > 0

    def test_non_json_model_response_returns_422(self):
        with _mock_ask("Sorry, I cannot help with that."):
            resp = client.post("/plan/intake", json={"user_input": {}})
        assert resp.status_code == 422

    def test_empty_user_input_does_not_crash(self):
        with _mock_ask("not json"):
            resp = client.post("/plan/intake", json={"user_input": {}})
        # Must return something, not a 500
        assert resp.status_code in (200, 422)
