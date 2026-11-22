import json
import pytest

from backend.app.fake_model import create_fake_model


PASSAGES = [
    {"text": "- **Amber Fort** — historic fort in Amer.", "section": "Sights",
     "source_name": "Jaipur Guide", "source_url": "https://example.test/fort"},
    {"text": "- Baga Beach &mdash; local food stalls in North Goa.\n- Anjuna beach — flea market in Bardez.",
     "section": "Beaches", "source_name": "Goa Guide", "source_url": "https://example.test/beaches"},
    {"text": "- Panjim Cafe — serves breakfast and snacks in Panjim.\n- Fort Aguada — a historic site in Bardez district.",
     "section": "Places", "source_name": "Goa Guide", "source_url": "https://example.test/places"},
    {"text": "- Chapora — home of the Chapora fort in North Goa.\n- **Kitesurfing** &mdash; try the activity near Morjim.\n- Vagator beach — a beach in Bardez.",
     "section": "Activities", "source_name": "Goa Guide", "source_url": "https://example.test/activities"},
]
COSTS = {"typical_entry_fee_low": 42, "meal_budget": 123}
BANNED = {"if", "this", "the", "it", "you", "there", "once", "now", "indian", "southern", "beaches"}


@pytest.mark.parametrize(("style", "expected_count"), [("relaxed", 3), ("packed", 4)])
def test_fake_plan_uses_unique_items_and_city_costs_for_each_style(style, expected_count):
    request = {"destination": "Goa", "days": 2, "budget": 10000,
               "interests": ["history", "food"], "style": style, "start_date": None}
    fake = create_fake_model(request)
    fake.set_passages(PASSAGES)
    fake.set_costs(COSTS)
    result = json.loads(fake("Create a travel itinerary"))

    assert len(result["days"]) == 2
    assert [len(day["stops"]) for day in result["days"]] == [expected_count, expected_count]
    stops = [stop for day in result["days"] for stop in day["stops"]]
    names = [stop["name"] for stop in stops]
    assert len(names) == len(set(name.casefold() for name in names))
    assert len(names) == 6 if style == "relaxed" else len(names) == 8
    for day in result["days"]:
        assert [stop["time_slot"] for stop in day["stops"]] == (
            ["morning", "afternoon", "evening"] if style == "relaxed"
            else ["morning", "afternoon", "evening", "evening"]
        )
    for stop in stops:
        assert 1 <= len(stop["name"].split()) <= 5
        assert not stop["name"][0].isdigit()
        assert stop["name"].split()[0].casefold() not in BANNED
        assert stop["name"].casefold() != "goa"
        assert stop["passage_ids"]
        assert 0 < len(stop["excerpt"]) <= 200
        assert "passage_text" not in stop
        assert "&mdash;" not in stop["excerpt"] and "**" not in stop["excerpt"]
        source_passage = PASSAGES[stop["passage_ids"][0] - 1]
        assert source_passage["source_name"]
        assert stop["est_cost_inr"] in {COSTS["meal_budget"], COSTS["typical_entry_fee_low"]}
        assert "Offline sample" in stop["notes"]
    assert next(stop for stop in stops if stop["name"] == "Baga Beach")["area"] == "North Goa"
    assert next(stop for stop in stops if stop["name"] == "Fort Aguada")["area"] == "Bardez"


def test_invalid_or_fragment_items_use_section_heading_fallback():
    fake = create_fake_model({"destination": "Goa", "days": 1, "style": "relaxed"})
    fake.set_passages([{
        "text": "- Indian — phrase fragment. - Southern — another fragment. - 1. Beaches Goa — heading fragment.",
        "section": "Beaches", "source_name": "Guide", "source_url": "https://example.test",
    }])
    result = json.loads(fake("draft"))
    stop = result["days"][0]["stops"][0]
    assert stop["name"] == "Guide Goa"
    assert len(stop["name"].split()) <= 5


def test_fake_model_produces_fewer_stops_instead_of_repeating_items():
    fake = create_fake_model({"destination": "Goa", "days": 2, "style": "relaxed"})
    fake.set_passages([{
        "text": "- Chapora — home of the fort. - Agonda — a quiet beach.",
        "section": "Places", "source_name": "Guide", "source_url": "https://example.test",
    }])
    result = json.loads(fake("draft"))
    assert [len(day["stops"]) for day in result["days"]] == [2, 0]
    names = [stop["name"] for day in result["days"] for stop in day["stops"]]
    assert len(names) == len(set(names))


def test_fake_model_handles_intake_prompt():
    request = {"destination": "Goa", "days": 1, "budget": 2000,
               "interests": ["beach"], "style": "relaxed", "start_date": None}
    assert json.loads(create_fake_model(request)("Parse the user's trip request")) == request
