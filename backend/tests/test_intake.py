"""
Tests for the intake node — task 1.4.

Required by the brief:
  1. Normal happy path → returns {"request": ...}
  2. Missing budget   → returns {"feedback": [...]}
  3. Nonsense destination → returns {"feedback": [...]}

Additional tests:
  4. Model returns malformed JSON → returns {"feedback": [...]} without crashing
  5. Model returns JSON with markdown fences → parsed correctly
  6. LLM is never called with a real key (all calls mocked)
"""
import json
from unittest.mock import patch

import pytest

from backend.app.graph.nodes import intake


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_ask(response_text: str):
    """Context manager that replaces ask() with a fixed response."""
    return patch("backend.app.graph.nodes.ask", return_value=response_text)


VALID_JSON = json.dumps({
    "destination": "Jaipur",
    "days": 3,
    "budget": 8000,
    "interests": ["history", "food"],
    "style": "relaxed",
})

MISSING_BUDGET_JSON = json.dumps({
    "destination": "Goa",
    "days": 2,
    "interests": ["beach"],
    "style": "packed",
    # budget deliberately omitted
})

BAD_DESTINATION_JSON = json.dumps({
    "destination": "Atlantis",   # not Jaipur/Chennai/Goa
    "days": 3,
    "budget": 5000,
    "interests": ["sightseeing"],
    "style": "relaxed",
})


# ---------------------------------------------------------------------------
# Test 1: Normal happy path
# ---------------------------------------------------------------------------

class TestIntakeNormal:
    def test_returns_request_on_valid_model_output(self):
        state = {"user_input": {"raw": "3 days in Jaipur, budget 8000 INR, interested in history and food"}}
        with _mock_ask(VALID_JSON):
            result = intake(state)

        assert "request" in result
        assert "feedback" not in result
        req = result["request"]
        assert req["destination"] == "Jaipur"
        assert req["days"] == 3
        assert req["budget"] == 8000
        assert "history" in req["interests"]
        assert req["style"] == "relaxed"

    def test_returns_request_when_model_wraps_in_markdown(self):
        fenced = f"```json\n{VALID_JSON}\n```"
        state = {"user_input": {"raw": "Jaipur 3 days"}}
        with _mock_ask(fenced):
            result = intake(state)

        assert "request" in result
        assert result["request"]["destination"] == "Jaipur"


# ---------------------------------------------------------------------------
# Test 2: Missing budget
# ---------------------------------------------------------------------------

class TestIntakeMissingBudget:
    def test_returns_feedback_when_budget_missing(self):
        state = {"user_input": {"raw": "2 days in Goa, packed style, beach"}}
        with _mock_ask(MISSING_BUDGET_JSON):
            result = intake(state)

        assert "feedback" in result
        assert isinstance(result["feedback"], list)
        assert len(result["feedback"]) > 0
        # "request" must NOT be present on failure
        assert "request" not in result

    def test_does_not_crash_on_missing_budget(self):
        state = {"user_input": {}}
        with _mock_ask(MISSING_BUDGET_JSON):
            result = intake(state)   # must not raise
        assert "feedback" in result


# ---------------------------------------------------------------------------
# Test 3: Nonsense destination
# ---------------------------------------------------------------------------

class TestIntakeNonsenseDestination:
    def test_returns_feedback_for_unsupported_city(self):
        state = {"user_input": {"raw": "Take me to Atlantis for 3 days"}}
        with _mock_ask(BAD_DESTINATION_JSON):
            result = intake(state)

        assert "feedback" in result
        assert "request" not in result

    def test_does_not_crash_on_nonsense_destination(self):
        state = {"user_input": {"destination": "Mars"}}
        with _mock_ask(BAD_DESTINATION_JSON):
            result = intake(state)   # must not raise
        assert "feedback" in result


# ---------------------------------------------------------------------------
# Test 4: Malformed JSON from model
# ---------------------------------------------------------------------------

class TestIntakeMalformedJSON:
    def test_returns_feedback_on_non_json_response(self):
        state = {"user_input": {"raw": "gibberish"}}
        with _mock_ask("I am sorry, I cannot help with that."):
            result = intake(state)

        assert "feedback" in result
        assert "request" not in result

    def test_returns_feedback_on_truncated_json(self):
        state = {"user_input": {}}
        with _mock_ask('{"destination": "Goa", "days": '):
            result = intake(state)

        assert "feedback" in result


# ---------------------------------------------------------------------------
# Optional start_date support
# ---------------------------------------------------------------------------

WITH_DATE_JSON = json.dumps({
    "destination": "Jaipur",
    "days": 3,
    "budget": 8000,
    "interests": ["history"],
    "style": "relaxed",
    "start_date": "2026-12-01",
})


class TestIntakeStartDate:
    def test_accepts_optional_start_date(self):
        state = {"user_input": {"raw": "Jaipur for 3 days from 2026-12-01"}}
        with _mock_ask(WITH_DATE_JSON):
            result = intake(state)

        assert result["request"]["start_date"] == "2026-12-01"

    def test_start_date_defaults_to_none_when_absent(self):
        state = {"user_input": {"raw": "Jaipur for 3 days"}}
        with _mock_ask(VALID_JSON):
            result = intake(state)

        assert result["request"]["start_date"] is None

    def test_prompt_asks_for_an_optional_start_date(self):
        with patch("backend.app.graph.nodes.ask", return_value=VALID_JSON) as mocked:
            intake({"user_input": {}})

        prompt = mocked.call_args.args[0]
        assert "start_date" in prompt
        assert "optional" in prompt

    def test_rejects_invalid_start_date(self):
        payload = json.dumps({
            "destination": "Goa",
            "days": 2,
            "budget": 5000,
            "interests": ["beach"],
            "style": "relaxed",
            "start_date": "next week",
        })
        with _mock_ask(payload):
            result = intake({"user_input": {"raw": "Goa next week"}})

        assert "feedback" in result
        assert "request" not in result
