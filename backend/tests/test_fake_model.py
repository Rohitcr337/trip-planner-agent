import json

import pytest

from backend.app.fake_model import create_fake_model


PASSAGES = [
    {"text": "The Amber Fort is a historic fort in Amer.", "section": "Amber Fort",
     "source_name": "Jaipur Guide", "source_url": "https://example.test/fort"},
    {"text": "Local food stalls serve traditional dishes at Baga Beach.", "section": "Food and dining",
     "source_name": "Goa Guide", "source_url": "https://example.test/food"},
    {"text": "A quiet garden sits near the city museum.", "section": "City Garden",
     "source_name": "Jaipur Guide", "source_url": "https://example.test/garden"},
    {"text": "Cafes offer breakfast and snacks in Panjim.", "section": "Cafes",
     "source_name": "Goa Guide", "source_url": "https://example.test/cafe"},
]
COSTS = {"typical_entry_fee_low": 42, "meal_budget": 123}


@pytest.mark.parametrize(("style", "expected_count"), [("relaxed", 3), ("packed", 4)])
def test_fake_plan_uses_passages_and_city_costs_for_each_style(style, expected_count):
    request = {"destination": "Jaipur", "days": 2, "budget": 10000,
               "interests": ["history", "food"], "style": style, "start_date": None}
    fake = create_fake_model(request)
    fake.set_passages(PASSAGES)
    fake.set_costs(COSTS)
    result = json.loads(fake("Create a travel itinerary"))

    assert len(result["days"]) == 2
    for day in result["days"]:
        assert len(day["stops"]) == expected_count
        assert [stop["time_slot"] for stop in day["stops"]] == (
            ["morning", "afternoon", "evening"] if style == "relaxed"
            else ["morning", "afternoon", "evening", "evening"]
        )
        for stop in day["stops"]:
            passage = PASSAGES[stop["passage_ids"][0] - 1]
            assert stop["passage_text"] == passage["text"]
            assert stop["name"] != "Jaipur"
            assert stop["name"].startswith(passage["section"])
            if passage is PASSAGES[0]:
                assert stop["area"] == "Amer"
            if passage is PASSAGES[1]:
                assert stop["area"] == "Baga Beach"
            expected_cost = COSTS["meal_budget"] if any(
                term in f"{passage['section']} {passage['text']}".casefold()
                for term in ("food", "cafe", "cafes")
            ) else COSTS["typical_entry_fee_low"]
            assert stop["est_cost_inr"] == expected_cost
            assert "Offline sample" in stop["notes"]


def test_fake_model_handles_intake_prompt():
    request = {"destination": "Goa", "days": 1, "budget": 2000,
               "interests": ["beach"], "style": "relaxed", "start_date": None}
    assert json.loads(create_fake_model(request)("Parse the user's trip request")) == request
