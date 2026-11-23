from backend.app.fake_model import create_fake_model
from backend.app.graph.build import build_planning_graph


REQUEST = {
    "destination": "Jaipur", "days": 1, "budget": 10000,
    "interests": ["history"], "style": "relaxed", "start_date": "2026-12-01",
    "avoid": [],
}
COSTS = {
    "available": True, "complete": True, "meal_budget": 200,
    "local_transport_per_day": 100, "typical_entry_fee_low": 100,
    "typical_entry_fee_high": 200, "stay_budget_per_night": 500,
}
INDOOR_PASSAGES = [
    {"text": "- City Museum — Explore the local history collection in the indoor museum galleries.", "section": "See", "source_name": "Guide", "source_url": "https://example.test/museum"},
    {"text": "- Amber Palace — The palace interior contains historic rooms and detailed stone carvings.", "section": "See", "source_name": "Guide", "source_url": "https://example.test/palace"},
    {"text": "- Heritage Gallery — View regional art and artifacts inside this public gallery space.", "section": "Do", "source_name": "Guide", "source_url": "https://example.test/gallery"},
]
MIXED_PASSAGES = [
    INDOOR_PASSAGES[0],
    {"text": "- Riverfront Park — Walk along the riverside park trails and open lawns.", "section": "See", "source_name": "Guide", "source_url": "https://example.test/park"},
    {"text": "- Sunset Viewpoint — See wide views over the open countryside from here.", "section": "See", "source_name": "Guide", "source_url": "https://example.test/view"},
]


def invoke_with_weather(monkeypatch, passages):
    from backend.app.graph import nodes

    monkeypatch.setattr(nodes, "retrieve", lambda city, query, k=4: passages)
    monkeypatch.setattr(nodes, "retrieve_activity_passages", lambda city, interests: [])
    monkeypatch.setattr(nodes, "load_costs", lambda city: COSTS)
    monkeypatch.setattr(nodes, "get_weather", lambda city, start, days: {
        "available": True, "reason": None,
        "days": [{"date": "2026-12-01", "temp_max_c": 28, "temp_min_c": 20, "precip_mm": 14, "rainy": True}],
    })
    monkeypatch.setattr(nodes, "geocode", lambda name, city: None)
    fake = create_fake_model(REQUEST)
    return build_planning_graph().invoke({
        "user_input": REQUEST, "request": REQUEST, "passages": [], "live_data": {},
        "draft": None, "feedback": [], "revisions": 0, "checks": [],
        "unresolved": [], "fake_model": fake,
    })


def test_rainy_sample_prioritizes_indoor_stops_and_passes_without_revisions(monkeypatch):
    state = invoke_with_weather(monkeypatch, INDOOR_PASSAGES)
    stops = state["draft"]["days"][0]["stops"]
    assert len(stops) == 3
    assert all(stop["outdoor"] is False for stop in stops)
    assert state["revisions"] == 0
    assert all(item["passed"] for item in state["checks"])


def test_rainy_sample_reports_unresolved_when_indoor_items_run_out(monkeypatch):
    state = invoke_with_weather(monkeypatch, MIXED_PASSAGES)
    assert state["draft"] is not None
    assert state["revisions"] == 3
    assert state["unresolved"]
    assert any("rainy day" in reason for reason in state["unresolved"])


def test_outdoor_classification_uses_names_and_first_description_sentence():
    from backend.app.fake_model import FakeModel

    def item(name, description, section="See"):
        return {"name": name, "description": description, "passage": {"section": section}}

    assert FakeModel._outdoor(item("Marina", "A popular beach with open sand.")) is True
    assert FakeModel._outdoor(item("Art House", "Contains a public gallery of regional art.")) is False
    assert FakeModel._outdoor(item("Pondy Bazaar", "A popular place to walk.")) is None
    assert FakeModel._outdoor(item("Cafe", "An indoor restaurant for local meals.", "Eat")) is False
