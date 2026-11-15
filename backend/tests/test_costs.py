"""
Tests for load_costs — task 3.3.

Every test points COSTS_PATH at a small fake file in tmp_path;
the real data/costs.json is never read.
"""
import json

import pytest

from backend.app import costs

FAKE_COSTS = {
    "note": "Fake data for tests.",
    "Completeville": {
        "meal_budget": 100,
        "meal_mid": 300,
        "local_transport_per_day": 50,
        "typical_entry_fee_low": 20,
        "typical_entry_fee_high": 200,
        "stay_budget_per_night": 800,
        "stay_mid_per_night": 2500,
    },
    "Halfville": {
        "meal_budget": 120,
        "meal_mid": None,
        "local_transport_per_day": 60,
        "typical_entry_fee_low": None,
        "typical_entry_fee_high": 150,
        "stay_budget_per_night": 900,
        "stay_mid_per_night": None,
    },
}


@pytest.fixture(autouse=True)
def fake_costs_file(tmp_path, monkeypatch):
    path = tmp_path / "costs.json"
    path.write_text(json.dumps(FAKE_COSTS), encoding="utf-8")
    monkeypatch.setattr(costs, "COSTS_PATH", path)


class TestLoadCosts:
    def test_complete_city_returns_values_and_true(self):
        result = costs.load_costs("Completeville")

        assert result["meal_budget"] == 100
        assert result["stay_mid_per_night"] == 2500
        assert result["complete"] is True
        assert "note" not in result

    def test_city_with_nulls_is_incomplete(self):
        result = costs.load_costs("Halfville")

        assert result["meal_mid"] is None
        assert result["typical_entry_fee_low"] is None
        assert result["complete"] is False

    def test_unknown_city_raises_clear_error(self):
        with pytest.raises(ValueError) as exc_info:
            costs.load_costs("Atlantis")

        message = str(exc_info.value)
        assert "Unknown city" in message
        assert "Atlantis" in message
        assert "Completeville" in message

    def test_note_is_not_treated_as_a_city(self):
        with pytest.raises(ValueError):
            costs.load_costs("note")

    def test_missing_field_raises_clear_error(self, tmp_path, monkeypatch):
        broken = {"Brokenville": {"meal_budget": 100}}
        path = tmp_path / "broken.json"
        path.write_text(json.dumps(broken), encoding="utf-8")
        monkeypatch.setattr(costs, "COSTS_PATH", path)

        with pytest.raises(ValueError) as exc_info:
            costs.load_costs("Brokenville")

        assert "missing fields" in str(exc_info.value)

    def test_missing_file_raises_clear_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(costs, "COSTS_PATH", tmp_path / "nope.json")

        with pytest.raises(RuntimeError) as exc_info:
            costs.load_costs("Completeville")

        assert "not found" in str(exc_info.value)
