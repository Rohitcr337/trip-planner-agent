import json
import pytest

from backend.app.fake_model import (
    _all_items,
    _clean_excerpt,
    _normalise_excerpt,
    _passage_items,
    _skip_item,
    _valid_excerpt,
    _valid_name,
    create_fake_model,
)
from backend.app.graph.nodes import retrieve_node
from backend.app.costs import load_costs
from backend.app.itinerary import kind_from_section


PASSAGES = [
    {"text": "- **Amber Fort** — a historic fort standing above Amer with old stone walls.", "section": "See",
     "source_name": "Jaipur Guide", "source_url": "https://example.test/fort"},
    {"text": "- Baga Beach &mdash; local food stalls serving fresh snacks and meals in North Goa.\n- Anjuna beach — a lively flea market operating every day along the Bardez coast.",
     "section": "See", "source_name": "Goa Guide", "source_url": "https://example.test/beaches"},
    {"text": "- Panjim Cafe — serves breakfast and snacks at a popular cafe in Panjim each morning.\n- Fort Aguada — a historic site with broad views across Bardez district and nearby coastline.",
     "section": "Eat", "source_name": "Goa Guide", "source_url": "https://example.test/places"},
    {"text": "- Chapora — home of the Chapora fort with wide views across North Goa.\n- **Kitesurfing** &mdash; try this popular water activity near Morjim during a windy afternoon.\n- Vagator beach — a quiet beach with cafes and swimming spots in Bardez district.",
     "section": "Do", "source_name": "Goa Guide", "source_url": "https://example.test/activities"},
]
COSTS = {
    "typical_entry_fee_low": 42,
    "typical_entry_fee_high": 84,
    "meal_budget": 123,
}
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
    counts = [len(day["stops"]) for day in result["days"]]
    assert counts == ([3, 2] if style == "relaxed" else [4, 3])
    stops = [stop for day in result["days"] for stop in day["stops"]]
    names = [stop["name"] for stop in stops]
    assert len(names) == len(set(name.casefold() for name in names))
    assert len(names) == (5 if style == "relaxed" else 7)
    for day in result["days"]:
        time_slots = [stop["time_slot"] for stop in day["stops"]]
        assert time_slots[0] == "morning"
        assert all(slot in {"morning", "afternoon", "evening"} for slot in time_slots)
        food_stops = [stop for stop in day["stops"] if stop["kind"] == "food"]
        assert all(stop["time_slot"] == "evening" for stop in food_stops)
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
        expected_kind = {"see": "sight", "do": "activity", "eat": "food", "drink": "food"}[
            source_passage["section"].casefold()
        ]
        assert stop["kind"] == expected_kind
        if expected_kind == "food":
            expected_cost = COSTS["meal_budget"]
        elif expected_kind == "activity":
            expected_cost = (
                COSTS["typical_entry_fee_low"] + COSTS["typical_entry_fee_high"]
            ) / 2
        else:
            expected_cost = COSTS["typical_entry_fee_low"]
        assert stop["est_cost_inr"] == expected_cost
        assert "Offline sample" in stop["notes"]
    assert next(stop for stop in stops if stop["name"] == "Baga Beach")["area"] == "North Goa"
    assert next(stop for stop in stops if stop["name"] == "Fort Aguada")["area"] == "Bardez"


def test_invalid_or_fragment_items_do_not_use_section_heading_fallback():
    fake = create_fake_model({"destination": "Goa", "days": 1, "style": "relaxed"})
    fake.set_passages([{
        "text": "- Indian &mdash; phrase fragment. - Southern &mdash; another fragment. - 1. Beaches Goa &mdash; heading fragment.",
        "section": "See", "source_name": "Guide", "source_url": "https://example.test",
    }])
    result = json.loads(fake("draft"))
    assert result["days"][0]["stops"] == []


def test_fake_model_produces_fewer_stops_instead_of_repeating_items():
    fake = create_fake_model({"destination": "Goa", "days": 2, "style": "relaxed"})
    fake.set_passages([{
        "text": "- Chapora — home of the historic fort with views across the green coast. - Agonda — a quiet beach with soft sand and small local cafes.",
        "section": "See", "source_name": "Guide", "source_url": "https://example.test",
    }])
    result = json.loads(fake("draft"))
    assert [len(day["stops"]) for day in result["days"]] == [1, 1]
    names = [stop["name"] for day in result["days"] for stop in day["stops"]]
    assert len(names) == len(set(names))
    assert "Limited sample content for this destination." in result["assumptions"]


def test_unstructured_passage_uses_a_place_name_from_its_text():
    passage = {
        "text": "Maharaja Ram Singh also built the Ramgarh Lake to supply water to the city.",
        "section": "Understand", "source_name": "Guide", "source_url": "https://example.test",
    }
    items = _passage_items(passage, 0, "Jaipur")
    assert items == []


@pytest.mark.parametrize("section", [
    "Understand", "Overview", "Get in", "Get around", "Sleep", "Accommodation",
    "Buy", "Shopping", "Stay safe", "Talk", "Connect", "Cope", "Beaches",
])
def test_non_activity_sections_never_create_sample_stops(section):
    fake = create_fake_model({"destination": "Goa", "days": 1, "style": "relaxed"})
    fake.set_passages([{
        "text": "- Chapora — a historic fort. - Baga Beach — a sandy beach.",
        "section": section, "source_name": "Guide", "source_url": "https://example.test",
    }])
    result = json.loads(fake("draft"))
    assert result["days"][0]["stops"] == []


def test_activity_section_matching_is_case_insensitive():
    items = _passage_items({
        "text": "- Chapora — a historic fort with broad views across the coastline.", "section": "sEe",
    }, 0, "Goa")
    assert [item["name"] for item in items] == ["Chapora"]


@pytest.mark.parametrize("name", [
    "Bangladesh", "Bangladeshi", "India", "Indian", "Rajasthan", "Tamil Nadu",
    "South Asia", "North Goa", "Central Chennai", "North Jaipur", "East Goa",
])
def test_non_attraction_and_city_direction_names_are_rejected(name):
    from backend.app.fake_model import _valid_name

    assert _valid_name(name, "Chennai") is None


def test_items_need_at_least_six_description_words():
    items = _passage_items({
        "text": "- Amber Fort \u2014 famous old fort with history.", "section": "See",
    }, 0, "Jaipur")
    assert items == []


def test_overlapping_stop_names_do_not_repeat_places():
    items = _all_items([{
        "text": "- Pondy Bazaar — a crowded market with many small shops and stalls. "
                "- Pondy Bazaar and Ranganathan Street — a lively shopping stretch with shops and food stalls. "
                "- Ranganathan Street — a busy street with many shops and local food stalls.",
        "section": "Do",
    }], "Chennai")
    assert [item["name"] for item in items] == ["Pondy Bazaar", "Ranganathan Street"]


@pytest.mark.parametrize("city", ["Jaipur", "Chennai", "Goa"])
@pytest.mark.parametrize("interests", [["beaches", "food"], ["history", "culture"]])
def test_offline_sample_backfills_each_day_with_unique_guide_stops(city, interests):
    request = {
        "destination": city, "days": 2, "budget": 50000,
        "interests": interests, "style": "relaxed", "start_date": None,
    }
    fake = create_fake_model(request)
    state = retrieve_node({"request": request, "passages": [], "fake_model": fake})
    fake.set_costs(load_costs(city))
    draft = json.loads(fake("Create a travel itinerary"))
    counts = [len(day["stops"]) for day in draft["days"]]
    stops = [stop for day in draft["days"] for stop in day["stops"]]
    names = [stop["name"].casefold() for stop in stops]

    assert counts == ([2, 2] if city == "Jaipur" else [3, 3])
    assert len(names) == len(set(names))
    assert all(stop["passage_ids"] and stop["kind"] in {"sight", "activity", "food"} for stop in stops)
    assert len(state["passages"]) >= len(stops)
    for stop in stops:
        cited = state["passages"][stop["passage_ids"][0] - 1]
        assert stop["kind"] == kind_from_section(cited["section"])


def test_fake_model_handles_intake_prompt():
    request = {"destination": "Goa", "days": 1, "budget": 2000,
               "interests": ["beach"], "style": "relaxed", "start_date": None}
    assert json.loads(create_fake_model(request)("Parse the user's trip request")) == request


def test_clean_excerpt_removes_leading_markers_and_collapses_dash_runs():
    cleaned = _clean_excerpt("- * - old city walk - with shaded lanes and local shops.")
    assert cleaned.startswith("Old city")
    assert " - " not in cleaned


def test_clean_excerpt_ends_at_a_complete_sentence_within_limit():
    cleaned = _clean_excerpt(
        "A garden has many shaded walks. Another complete sentence explains the fountain. "
        "A later sentence should not be needed.",
        maximum=65,
    )
    assert cleaned.endswith(".")
    assert len(cleaned) <= 65


def test_clean_excerpt_uses_ellipsis_when_no_complete_sentence_fits():
    cleaned = _clean_excerpt(
        "This is a very long description without any complete sentence inside the short prefix",
        maximum=45,
    )
    assert cleaned.endswith("...")


@pytest.mark.parametrize("description", [
    "Small place.",
    "- - Cricket: - - - Parks - - Nearby - Festivals",
    "- - Cricket - - Parks - - Nearby - Festivals",
])
def test_fragment_excerpts_are_rejected(description):
    assert not _valid_excerpt(description)


def test_unbalanced_name_bracket_drops_matched_opening_and_tail():
    assert _valid_name("Elliots Beach (Besant Nagar", "Chennai") == "Elliots Beach"


def test_trailing_name_punctuation_is_removed():
    assert _valid_name("Marina Beach!!!", "Chennai") == "Marina Beach"


def test_no_two_items_share_a_normalised_excerpt():
    items = _all_items([{
        "text": "- Lake Palace — a quiet palace with shaded gardens and a calm lakeside view. "
                "- Old Palace — a quiet palace with shaded gardens and a calm lakeside view.",
        "section": "See",
    }], "Jaipur")
    assert len(items) == 1


@pytest.mark.parametrize(("name", "description"), [
    ("Gangaur Festival", "A colourful celebration with music and decorated streets."),
    ("Summer Parade", "A public event that takes place every year."),
    ("Old Bazaar Fair", "The fair is held every March with stalls and local crafts."),
])
def test_dated_events_are_skipped(name, description):
    assert _skip_item(name, description)


def test_description_is_only_dated_when_first_sentence_has_event_and_date_language():
    assert _skip_item(
        "City Museum",
        "A ceremony is held in January. Visitors can tour galleries throughout the year.",
    )
    assert not _skip_item(
        "City Museum",
        "A ceremony welcomes visitors. The museum opens throughout the year.",
    )


@pytest.mark.parametrize(("name", "description"), [
    ("Cricket", "A popular sport played on open grounds with local teams."),
    ("Football", "A team sport played in a large outdoor stadium."),
    ("Hockey", "An evening game watched by enthusiastic local supporters."),
])
def test_sports_as_standalone_non_visit_names_are_skipped(name, description):
    assert _skip_item(name, description)


def test_sport_name_with_place_word_is_kept():
    assert not _skip_item(
        "Cricket Fort",
        "A former fort where local matches are sometimes played on the grounds.",
    )


def test_passage_items_skip_events_and_standalone_sports():
    items = _passage_items({
        "text": "- Gangaur Festival — a colourful festival held in March with crowds and music. "
                "- Cricket — a popular sport played on open grounds with local teams.",
        "section": "Do",
    }, 0, "Jaipur")
    assert items == []


def test_activity_cost_uses_midpoint_and_sight_cost_uses_low():
    request = {
        "destination": "Goa", "days": 1, "budget": 5000,
        "interests": ["beach"], "style": "relaxed", "start_date": None,
    }
    fake = create_fake_model(request)
    fake.set_passages([
        {
            "text": "- Kitesurfing — try this popular water activity near Morjim during a windy afternoon.",
            "section": "Do", "source_name": "Guide", "source_url": "https://example.test",
        },
        {
            "text": "- Fort Aguada — a historic fort with broad views across the coastline.",
            "section": "See", "source_name": "Guide", "source_url": "https://example.test",
        },
    ])
    fake.set_costs(COSTS)
    stops = json.loads(fake("draft"))["days"][0]["stops"]
    costs = {stop["kind"]: stop["est_cost_inr"] for stop in stops}
    assert costs["activity"] == 63
    assert costs["sight"] == 42


@pytest.mark.parametrize("interest", ["food", "eat", "restaurant", "cuisine", "dining"])
def test_food_interests_add_one_evening_food_stop_per_day(interest):
    request = {
        "destination": "Goa", "days": 2, "budget": 5000,
        "interests": [interest], "style": "relaxed", "start_date": None,
    }
    fake = create_fake_model(request)
    fake.set_passages([
        {
            "text": "- Panjim Cafe — serves breakfast and snacks at a popular cafe in Panjim each morning.",
            "section": "Eat", "source_name": "Guide", "source_url": "https://example.test",
        },
        {
            "text": "- Margao Market — serves local meals and snacks near shops and busy market lanes.",
            "section": "Eat", "source_name": "Guide", "source_url": "https://example.test",
        },
        {
            "text": "- Fort Aguada — a historic fort with broad views across the coastline.",
            "section": "See", "source_name": "Guide", "source_url": "https://example.test",
        },
        {
            "text": "- Baga Beach — a sandy beach with water sports and cafes along the coast.",
            "section": "See", "source_name": "Guide", "source_url": "https://example.test",
        },
    ])
    fake.set_costs(COSTS)
    result = json.loads(fake("draft"))
    all_stops = [stop for day in result["days"] for stop in day["stops"]]
    assert len(all_stops) == len({stop["name"].casefold() for stop in all_stops})
    assert all(
        any(stop["kind"] == "food" and stop["time_slot"] == "evening"
            for stop in day["stops"])
        for day in result["days"]
    )
