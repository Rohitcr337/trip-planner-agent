"""
graph/nodes.py — one function per graph node.

Every node receives the full TripState and returns a dict of keys to update.
All model calls go through ask() in llm.py.
Each node logs: node name, short input, short output, seconds taken.
"""
import json
import logging
import re
import time
from typing import Any

from pydantic import ValidationError

from backend.app.checks import run_checks
from backend.app.costs import load_costs
from backend.app.fake_model import excerpt_for_stop
from backend.app.graph.state import TripState
from backend.app.itinerary import Itinerary, Source, build_draft_prompt, kind_from_section
from backend.app.llm import ask
from backend.app.retrieve import retrieve, retrieve_activity_passages
from backend.app.schemas import TripRequest
from backend.app.tools import geocode, get_weather

logger = logging.getLogger(__name__)
DRAFT_PASSAGE_K = 8


def _call_model(prompt: str, state: TripState) -> str:
    fake_model = state.get("fake_model")
    return fake_model(prompt) if fake_model is not None else ask(prompt)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _log(node: str, short_input: str, short_output: str, elapsed: float) -> None:
    logger.info("[%s] in=%r out=%r (%.2fs)", node, short_input, short_output, elapsed)


def _extract_json(text: str) -> dict:
    """
    Pull the first JSON object out of a model response string.
    Raises ValueError if no valid JSON object is found.
    """
    # Strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first and last fence lines
        inner = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])
        text = inner.strip()

    # Find first { … } block
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in model response.")
    # Walk to find matching closing brace
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("Unmatched braces in model response.")


# ── Nodes ─────────────────────────────────────────────────────────────────────

def intake(state: TripState) -> TripState:
    """
    Intake node: parse and validate the user's raw input.

    Sends a structured prompt to the LLM, expects JSON matching TripRequest,
    validates it with Pydantic, and returns:
      - {"request": <dict>}           on success
      - {"feedback": [<reason str>]}  on any failure (never raises)
    """
    t0 = time.perf_counter()
    node = "intake"
    user_input = state.get("user_input", {})

    if state.get("request") is not None:
        try:
            req = TripRequest.model_validate(state["request"])
            result = req.model_dump()
            _log(node, "structured request", str(result)[:80], time.perf_counter() - t0)
            return {"request": result}
        except ValidationError as exc:
            reason = str(exc)
            _log(node, "structured request", f"feedback: {reason[:80]}", time.perf_counter() - t0)
            return {"feedback": [reason]}

    prompt = (
        "You are a trip-planning assistant. "
        "Parse the user's trip request and return ONLY a JSON object "
        "(no markdown, no explanation) with exactly these fields:\n"
        "  destination  — one of: Jaipur, Chennai, Goa\n"
        "  days         — integer 1–7\n"
        "  budget       — positive number (INR)\n"
        "  interests    — non-empty list of strings\n"
        "  style        — one of: relaxed, packed\n"
        "  start_date   — optional ISO date (YYYY-MM-DD) if the user gave one; "
        "otherwise null\n"
        "  avoid        — optional list of place names to avoid; otherwise []\n\n"
        f"User input:\n{json.dumps(user_input, ensure_ascii=False)}"
    )

    short_in = str(user_input)[:80]

    try:
        raw = _call_model(prompt, state)
        data = _extract_json(raw)
        req = TripRequest.model_validate(data)
        result = req.model_dump()
        elapsed = time.perf_counter() - t0
        _log(node, short_in, str(result)[:80], elapsed)
        return {"request": result}

    except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as exc:
        reason = str(exc)
        elapsed = time.perf_counter() - t0
        _log(node, short_in, f"feedback: {reason[:80]}", elapsed)
        return {"feedback": [reason]}


def retrieve_node(state: TripState) -> TripState:
    """Retrieve guide passages for the validated destination and interests."""
    t0 = time.perf_counter()
    request = state.get("request")
    if not request:
        _log("retrieve", "no request", "skipped", time.perf_counter() - t0)
        return state

    destination = request["destination"]
    interests = request.get("interests", [])
    query = " ".join([destination, *interests])
    queries = [query, *interests]
    food_words = {"food", "eat", "restaurant", "cuisine", "dining"}
    if any(
        interest_word.casefold() in food_words
        for interest in interests
        for interest_word in re.findall(r"[a-z]+", interest.casefold())
    ):
        queries.append("restaurants eat dining cuisine")
    ranked = []
    for query_index, retrieval_query in enumerate(queries):
        for rank, passage in enumerate(
            retrieve(destination, retrieval_query, k=DRAFT_PASSAGE_K), start=1
        ):
            ranked.append((rank, query_index, passage))
    ranked.sort(key=lambda item: (item[0], item[1]))
    passages = []
    seen = set()
    for _, _, passage in ranked:
        key = (
            passage.get("source_name"), passage.get("source_url"),
            passage.get("section"), passage.get("text"),
        )
        if key not in seen:
            seen.add(key)
            passages.append(passage)
    primary_passage_count = len(passages)
    fake_model = state.get("fake_model")
    if fake_model is not None:
        backfill = retrieve_activity_passages(destination, interests)
        for passage in backfill:
            key = (
                passage.get("source_name"), passage.get("source_url"),
                passage.get("section"), passage.get("text"),
            )
            if key not in seen:
                seen.add(key)
                passages.append(passage)
        fake_model.set_passages(passages, primary_count=primary_passage_count)
    result = dict(state)
    result["passages"] = passages
    _log("retrieve", query[:80], f"{len(passages)} passages", time.perf_counter() - t0)
    return result


def fetch_node(state: TripState) -> TripState:
    """Fetch live weather (when a start date exists) and city cost estimates."""
    t0 = time.perf_counter()
    request = state.get("request")
    if not request:
        _log("fetch", "no request", "skipped", time.perf_counter() - t0)
        return state

    city = request["destination"]
    days = request["days"]
    start_date = request.get("start_date")

    if start_date:
        try:
            weather = get_weather(city, start_date, days)
        except Exception as exc:  # the tool should not raise; never break the graph
            logger.exception("Weather tool raised unexpectedly")
            weather = {
                "available": False,
                "reason": f"Weather lookup failed: {exc}",
                "days": [],
            }
    else:
        weather = {
            "available": False,
            "reason": "No start date provided; weather not fetched.",
            "days": [],
        }

    try:
        city_costs = load_costs(city)
    except Exception as exc:  # cost data must never break the graph
        logger.exception("Cost lookup raised unexpectedly")
        city_costs = {"available": False, "reason": str(exc), "complete": False}

    fake_model = state.get("fake_model")
    if fake_model is not None:
        fake_model.set_costs(city_costs)
        fake_model.set_weather(weather)

    result = dict(state)
    result["live_data"] = {"weather": weather, "costs": city_costs, "city": city}
    _log(
        "fetch",
        f"{city} start={start_date}",
        f"weather={weather['available']} costs_complete={city_costs.get('complete')}",
        time.perf_counter() - t0,
    )
    return result


def draft_node(state: TripState) -> TripState:
    """Create and verify a structured itinerary draft from retrieved evidence."""
    t0 = time.perf_counter()
    request = state.get("request")
    if not request:
        _log("draft", "no request", "skipped", time.perf_counter() - t0)
        return state

    try:
        validated = _create_draft(state)
        result = dict(state)
        result["draft"] = validated
        _log("draft", request["destination"], f"{len(validated['days'])} days", time.perf_counter() - t0)
        return result
    except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as exc:
        result = dict(state)
        result["draft"] = None
        result["feedback"] = [*state.get("feedback", []), f"Draft could not be created: {exc}"]
        _log("draft", request["destination"], "feedback", time.perf_counter() - t0)
        return result


def locate_node(state: TripState) -> TripState:
    """Add real coordinates to stops when the optional geocoder can find them."""
    t0 = time.perf_counter()
    draft = state.get("draft")
    request = state.get("request") or {}
    if draft is None:
        _log("locate", "no draft", "skipped", time.perf_counter() - t0)
        return state

    located = dict(draft)
    city = request.get("destination", draft.get("city", ""))
    located_days = []
    count = 0
    for day in draft.get("days", []):
        located_day = dict(day)
        located_stops = []
        for stop in day.get("stops", []):
            located_stop = dict(stop)
            point = geocode(str(stop.get("name", "")), city)
            if point is None:
                located_stop["lat"] = None
                located_stop["lon"] = None
            else:
                located_stop["lat"], located_stop["lon"] = point
                count += 1
            located_stops.append(located_stop)
        located_day["stops"] = located_stops
        located_days.append(located_day)
    located["days"] = located_days
    result = dict(state)
    result["draft"] = located
    _log("locate", city, f"{count} stops located", time.perf_counter() - t0)
    return result


def _parse_and_validate_draft(raw: str, state: TripState) -> dict:
    """Parse itinerary JSON, validate its schema, and attach retrieved sources."""
    itinerary = Itinerary.model_validate(_extract_json(raw))
    passages = state.get("passages") or []
    for stop in (stop for day in itinerary.days for stop in day.stops):
        valid_ids = sorted(
            {passage_id for passage_id in stop.passage_ids
             if 1 <= passage_id <= len(passages)}
        )
        stop.passage_ids = valid_ids
        stop.sources = [
            Source(
                source_name=passages[passage_id - 1]["source_name"],
                source_url=passages[passage_id - 1]["source_url"],
                section=passages[passage_id - 1]["section"],
            )
            for passage_id in valid_ids
        ]
        stop.unverified = not stop.sources
        stop.kind = (
            kind_from_section(passages[valid_ids[0] - 1].get("section"))
            if valid_ids else None
        )
        stop.excerpt = (
            excerpt_for_stop(stop.name, passages[valid_ids[0] - 1], itinerary.city)
            if valid_ids else ""
        )
    return itinerary.model_dump(mode="json")


def _create_draft(
    state: TripState,
    feedback: list[str] | None = None,
    previous_draft: dict | None = None,
) -> dict:
    """Ask for an itinerary and return its validated, source-enriched form."""
    raw = _call_model(build_draft_prompt(state, feedback, previous_draft), state)
    return _parse_and_validate_draft(raw, state)


def check_node(state: TripState) -> TripState:
    """Run all deterministic checks and collect actionable revision feedback."""
    t0 = time.perf_counter()
    checks = run_checks(state)
    feedback = [
        item["reason"] for item in checks
        if not item["passed"] and not item["reason"].lower().startswith("skipped:")
    ]
    result = dict(state)
    result["checks"] = checks
    result["feedback"] = feedback
    _log("check", "draft", f"{len(feedback)} failing checks", time.perf_counter() - t0)
    return result


def revise_node(state: TripState) -> TripState:
    """Ask for a revision and retain the previous draft if parsing fails."""
    t0 = time.perf_counter()
    previous = state.get("draft")
    result = dict(state)
    try:
        result["draft"] = _create_draft(state, state.get("feedback", []), previous)
        _log("revise", str(state.get("revisions", 0)), "draft updated", time.perf_counter() - t0)
    except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as exc:
        result["draft"] = previous
        result["feedback"] = [*state.get("feedback", []), f"Revision could not be parsed; previous draft retained: {exc}"]
        _log("revise", str(state.get("revisions", 0)), "previous draft retained", time.perf_counter() - t0)
    result["revisions"] = int(state.get("revisions", 0)) + 1
    return result


def unresolved_node(state: TripState) -> TripState:
    """Record the check reasons that remain after the revision limit."""
    t0 = time.perf_counter()
    result = dict(state)
    result["unresolved"] = list(state.get("feedback", []))
    _log("unresolved", "revision limit", f"{len(result['unresolved'])} issues", time.perf_counter() - t0)
    return result
