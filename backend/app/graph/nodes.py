"""
graph/nodes.py — one function per graph node.

Every node receives the full TripState and returns a dict of keys to update.
All model calls go through ask() in llm.py.
Each node logs: node name, short input, short output, seconds taken.
"""
import json
import logging
import time

from pydantic import ValidationError

from backend.app.costs import load_costs
from backend.app.graph.state import TripState
from backend.app.itinerary import Itinerary, Source, build_draft_prompt
from backend.app.llm import ask
from backend.app.retrieve import retrieve
from backend.app.schemas import TripRequest
from backend.app.tools import get_weather

logger = logging.getLogger(__name__)

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
        "otherwise null\n\n"
        f"User input:\n{json.dumps(user_input, ensure_ascii=False)}"
    )

    short_in = str(user_input)[:80]

    try:
        raw = ask(prompt)
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
    passages = retrieve(destination, query)
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
        raw = ask(build_draft_prompt(state))
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

        result = dict(state)
        result["draft"] = itinerary.model_dump(mode="json")
        _log("draft", request["destination"], f"{len(itinerary.days)} days", time.perf_counter() - t0)
        return result
    except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as exc:
        result = dict(state)
        result["draft"] = None
        result["feedback"] = [*state.get("feedback", []), f"Draft could not be created: {exc}"]
        _log("draft", request["destination"], "feedback", time.perf_counter() - t0)
        return result
