"""
Tests for state.py and schemas.py — task 1.3.

Covers:
- TripState has the expected keys with correct types
- TripRequest validates correct input
- TripRequest rejects invalid destinations, out-of-range days/budget,
  empty interests, and bad style values
"""
import pytest
from pydantic import ValidationError

from backend.app.schemas import TripRequest
from backend.app.graph.state import TripState


# ---------------------------------------------------------------------------
# TripState
# ---------------------------------------------------------------------------

class TestTripState:
    def test_is_typed_dict(self):
        from typing import get_type_hints
        hints = get_type_hints(TripState)
        assert "user_input" in hints
        assert "request" in hints
        assert "passages" in hints
        assert "live_data" in hints
        assert "draft" in hints
        assert "feedback" in hints
        assert "revisions" in hints
        assert "checks" in hints
        assert "unresolved" in hints
        assert "fake_model" in hints

    def test_can_create_valid_state(self):
        state: TripState = {
            "user_input": {"destination": "Goa"},
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
        assert state["revisions"] == 0
        assert state["checks"] == []
        assert state["unresolved"] == []
        assert state["fake_model"] is None
        assert state["request"] is None
        assert state["passages"] == []


# ---------------------------------------------------------------------------
# TripRequest — valid cases
# ---------------------------------------------------------------------------

class TestTripRequestValid:
    def test_minimal_valid_request(self):
        req = TripRequest(
            destination="Jaipur",
            days=3,
            budget=5000.0,
            interests=["history"],
            style="relaxed",
        )
        assert req.destination == "Jaipur"
        assert req.days == 3
        assert req.budget == 5000.0
        assert req.style == "relaxed"

    def test_all_three_destinations_accepted(self):
        for city in ("Jaipur", "Chennai", "Goa"):
            req = TripRequest(
                destination=city,
                days=1,
                budget=1.0,
                interests=["food"],
                style="packed",
            )
            assert req.destination == city

    def test_days_boundary_1(self):
        req = TripRequest(
            destination="Goa", days=1, budget=100, interests=["beach"], style="relaxed"
        )
        assert req.days == 1

    def test_days_boundary_7(self):
        req = TripRequest(
            destination="Goa", days=7, budget=100, interests=["beach"], style="packed"
        )
        assert req.days == 7

    def test_multiple_interests(self):
        req = TripRequest(
            destination="Chennai",
            days=2,
            budget=3000,
            interests=["temples", "food", "music"],
            style="relaxed",
        )
        assert len(req.interests) == 3

    def test_optional_start_date_accepted(self):
        req = TripRequest(
            destination="Goa",
            days=2,
            budget=5000,
            interests=["beach"],
            style="relaxed",
            start_date="2026-12-01",
        )
        assert req.start_date == "2026-12-01"

    def test_start_date_defaults_to_none(self):
        req = TripRequest(
            destination="Goa",
            days=2,
            budget=5000,
            interests=["beach"],
            style="relaxed",
        )
        assert req.start_date is None


# ---------------------------------------------------------------------------
# TripRequest — invalid cases
# ---------------------------------------------------------------------------

class TestTripRequestInvalid:
    def test_rejects_unsupported_destination(self):
        with pytest.raises(ValidationError) as exc_info:
            TripRequest(
                destination="Mumbai",  # not allowed
                days=3,
                budget=5000,
                interests=["sightseeing"],
                style="relaxed",
            )
        assert "destination" in str(exc_info.value).lower() or "literal" in str(exc_info.value).lower()

    def test_rejects_days_zero(self):
        with pytest.raises(ValidationError):
            TripRequest(
                destination="Goa", days=0, budget=5000, interests=["beach"], style="relaxed"
            )

    def test_rejects_days_eight(self):
        with pytest.raises(ValidationError):
            TripRequest(
                destination="Goa", days=8, budget=5000, interests=["beach"], style="relaxed"
            )

    def test_rejects_negative_budget(self):
        with pytest.raises(ValidationError):
            TripRequest(
                destination="Jaipur", days=2, budget=-100, interests=["forts"], style="packed"
            )

    def test_rejects_zero_budget(self):
        with pytest.raises(ValidationError):
            TripRequest(
                destination="Jaipur", days=2, budget=0, interests=["forts"], style="packed"
            )

    def test_rejects_empty_interests(self):
        with pytest.raises(ValidationError):
            TripRequest(
                destination="Chennai", days=2, budget=2000, interests=[], style="relaxed"
            )

    def test_rejects_invalid_style(self):
        with pytest.raises(ValidationError):
            TripRequest(
                destination="Goa",
                days=3,
                budget=5000,
                interests=["beach"],
                style="moderate",  # not allowed
            )

    def test_rejects_invalid_start_date(self):
        with pytest.raises(ValidationError) as exc_info:
            TripRequest(
                destination="Goa",
                days=3,
                budget=5000,
                interests=["beach"],
                style="relaxed",
                start_date="next week",
            )
        assert "start_date" in str(exc_info.value)
