"""Deterministic local itinerary samples grounded in retrieved passages."""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

from backend.app.text import clean_text
from backend.app.itinerary import kind_from_section


TIME_SLOTS = {
    "relaxed": ("morning", "afternoon", "evening"),
    "packed": ("morning", "afternoon", "evening", "evening"),
}
OUTDOOR_TERMS = ("beach", "fort", "garden", "hill", "waterfall", "park", "lake", "outdoor")
BANNED_NAME_STARTS = {
    "a", "an", "and", "as", "at", "but", "by", "famous", "for", "from",
    "here", "if", "in", "indian", "it", "local", "many", "most", "now",
    "of", "once", "one", "our", "people", "several", "some", "southern",
    "northern", "eastern", "western", "the", "there", "they", "this", "visitors",
    "we", "you", "beaches", "tamil", "hindi", "marathi", "formerly",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december", "christianity",
    "catholic", "hindu", "india", "rajasthan", "thomas",
}
_NAME_TRAILING_WORDS = {"and", "&", "of", "the", "in", "at", "to", "or", "for", "from"}
_LIST_ITEM = re.compile(r"(?:^|\s)-\s+")
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_PLACE_SUFFIX = re.compile(
    r"\b((?:[A-Z][A-Za-z’'-]*|and|of|the|&)(?:\s+(?:[A-Z][A-Za-z’'-]*|and|of|the|&)){0,3}\s+"
    r"(?i:Fort|Lake|Temple|Palace|Beach|Market|Bazaar|Bazaars|Museum|Hill|Hills|Island|"
    r"Garden|Sanctuary|Falls|Waterfall|Church|Cathedral|Square|Street|Park|Village|Mall|Malls|"
    r"Chicken|Curry|Dosa|Thali|Biryani|Dhani))\b"
)
_CONTEXT_PLACE = re.compile(
    r"\b(?:in|near|at|to)\s+"
    r"((?:[A-Z][A-Za-z’'-]*|and|&)(?:\s+(?:[A-Z][A-Za-z’'-]*|and|&|of|the)){0,3})"
)
ACTIVITY_SECTIONS = {"see", "do", "eat", "drink"}
NON_ATTRACTION_NAMES = frozenset({
    "bangladesh", "bangladeshi", "india", "indian", "nepal", "nepali",
    "sri lanka", "sri lankan", "pakistan", "pakistani", "portugal", "portuguese",
    "rajasthan", "tamil nadu", "kerala", "karnataka", "maharashtra", "gujarat",
    "bihar", "uttar pradesh", "west bengal", "goa", "south asia", "north india",
    "south india", "east india", "west india", "central india", "asia", "europe",
    "africa", "middle east", "north goa", "south goa",
})
CITY_DIRECTION_WORDS = frozenset({"central", "north", "south", "east", "west"})
_DISTRICT_PATTERNS = (
    re.compile(r"\b(?:North|South)\s+Goa\b", re.IGNORECASE),
    re.compile(r"\bBardez\b", re.IGNORECASE),
    re.compile(
        r"\b([A-Z][A-Za-z'’.-]*(?:\s+[A-Z][A-Za-z'’.-]*){0,2})\s+(?:district|taluka)\b",
        re.IGNORECASE,
    ),
)


def _clean_bracketed_name(value: str) -> str:
    name = clean_text(value).strip()
    pairs = {"(": ")", "[": "]", "{": "}"}
    opening_positions: dict[str, list[int]] = {opening: [] for opening in pairs}
    for index, character in enumerate(name):
        if character in pairs:
            opening_positions[character].append(index)
        elif character in pairs.values():
            opener = next((open_char for open_char, close_char in pairs.items()
                           if close_char == character), None)
            if opener and opening_positions[opener]:
                opening_positions[opener].pop()
    unmatched = [
        positions[-1] for positions in opening_positions.values() if positions
    ]
    if unmatched:
        name = name[:min(unmatched)].rstrip()
    return name


def _valid_name(value: str, city: str) -> str | None:
    name = _clean_bracketed_name(value)
    name = name.strip(" \t\r\n:;,.!?—–-_'\"()[]{}")
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    words = name.split()
    while len(words) > 1 and words[0].casefold() in {"a", "an", "the", "at", "in"}:
        words.pop(0)
    name = " ".join(words)
    words = name.split()
    if not 1 <= len(words) <= 5 or name.casefold() == city.casefold():
        return None
    folded_name = name.casefold()
    if folded_name in NON_ATTRACTION_NAMES:
        return None
    if len(words) == 2 and words[0].casefold() in CITY_DIRECTION_WORDS:
        if words[1].casefold() in {"jaipur", "chennai", "goa"}:
            return None
    first = re.sub(r"[^A-Za-z]+$", "", words[0]).casefold()
    if (not first or first[0].isdigit() or first in BANNED_NAME_STARTS
            or words[-1].casefold().strip(".,;:") in _NAME_TRAILING_WORDS
            or not words[0][0].isupper()):
        return None
    return name


def _fallback_candidates(text: str, city: str, passage_index: int, passage: dict[str, Any]) -> list[dict[str, Any]]:
    raw = str(passage.get("text") or "")
    found: list[tuple[int, str]] = []
    for match in _BOLD.finditer(raw):
        value = next(group for group in match.groups() if group is not None)
        name = _valid_name(value, city)
        if name:
            found.append((match.start(), name))
    for match in _PLACE_SUFFIX.finditer(text):
        name = _valid_name(match.group(1), city)
        if name:
            found.append((match.start(), name))
    for match in _CONTEXT_PLACE.finditer(text):
        name = _valid_name(match.group(1), city)
        if name and _area_from_passage(name, city) == city:
            found.append((match.start(), name))

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for _, name in sorted(found, key=lambda item: item[0]):
        if name.casefold() in seen:
            continue
        sentence = next((part for part in sentences if name.casefold() in part.casefold()), text)
        description = _clean_excerpt(sentence)
        if not _valid_excerpt(description):
            continue
        items.append({
            "name": name,
            "description": description,
            "passage_index": passage_index,
            "passage": passage,
        })
        seen.add(name.casefold())
    return items


def _passage_items(passage: dict[str, Any], passage_index: int, city: str) -> list[dict[str, Any]]:
    section = clean_text(str(passage.get("section") or "").split(" > ")[-1]).casefold()
    if section not in ACTIVITY_SECTIONS:
        return []
    text = clean_text(str(passage.get("text") or ""))
    items: list[dict[str, Any]] = []
    has_item_separator = False
    for segment in _LIST_ITEM.split(text):
        if "—" not in segment:
            continue
        has_item_separator = True
        raw_name, raw_description = segment.split("—", 1)
        name = _valid_name(raw_name, city)
        description = _clean_excerpt(raw_description)
        if name and _valid_excerpt(description):
            items.append({
                "name": name,
                "description": description,
                "passage_index": passage_index,
                "passage": passage,
            })
    if not items and not has_item_separator:
        items = _fallback_candidates(text, city, passage_index, passage)
    return items


def _all_items(
    passages: list[dict[str, Any]], city: str, passage_offset: int = 0
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_excerpts: set[str] = set()
    for passage_index, passage in enumerate(passages, start=passage_offset):
        for item in _passage_items(passage, passage_index, city):
            excerpt_key = _normalise_excerpt(item["description"])
            if (excerpt_key not in seen_excerpts
                    and not any(_names_overlap(item["name"], existing["name"]) for existing in items)):
                items.append(item)
                seen_excerpts.add(excerpt_key)
    return items


def _names_overlap(first: str, second: str) -> bool:
    first_words = re.findall(r"[a-z0-9]+", first.casefold())
    second_words = re.findall(r"[a-z0-9]+", second.casefold())
    return any(
        first_words[start:start + len(second_words)] == second_words
        for start in range(len(first_words) - len(second_words) + 1)
    ) or any(
        second_words[start:start + len(first_words)] == first_words
        for start in range(len(second_words) - len(first_words) + 1)
    )


def _area_from_passage(text: str, city: str) -> str:
    text = clean_text(text)
    for pattern in _DISTRICT_PATTERNS:
        match = pattern.search(text)
        if match:
            return clean_text(match.group(1) if match.lastindex else match.group(0))
    return city


def _truncate_excerpt(value: str, maximum: int = 200) -> str:
    return _clean_excerpt(value, maximum)


def _clean_excerpt(value: str, maximum: int = 200) -> str:
    text = clean_text(value).strip(" \t\r\n:;,—–-_'\"")
    text = re.sub(r"^(?:[-*•]\s*)+", "", text)
    text = re.sub(r"\s+-\s+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" \t:;,—–-")
    if not text:
        return ""
    if text[0].islower():
        text = text[0].upper() + text[1:]

    if len(text) <= maximum:
        return text

    prefix = text[:maximum]
    complete_sentences = [
        match.end() for match in re.finditer(r"[.!?](?=\s|$)", prefix)
    ]
    if complete_sentences:
        text = prefix[:complete_sentences[-1]].strip()
    else:
        cut = prefix.rfind(" ")
        text = (prefix[:cut].rstrip(" ,;:-") if cut > 0 else "")
        if text:
            text += "..."
    return text


def _normalise_excerpt(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean_excerpt(value).casefold()).strip()


def _valid_excerpt(value: str) -> bool:
    text = clean_text(value)
    words = re.findall(r"[A-Za-z0-9]+", text)
    if len(words) < 6:
        return False
    tokens = re.findall(r"[^A-Za-z0-9\s]+|\S+", text)
    dash_colon_tokens = sum(
        1 for token in tokens
        if "-" in token or "–" in token or "—" in token or ":" in token
    )
    if tokens and dash_colon_tokens / len(tokens) > 0.25:
        return False
    if text[:80].count(" - ") >= 3:
        return False
    return True


def excerpt_for_stop(name: str, passage: dict[str, Any], city: str) -> str:
    """Return a short description for a stop from its supporting passage."""
    for item in _passage_items(passage, 0, city):
        if item["name"].casefold() == name.casefold():
            return _truncate_excerpt(item["description"])
    return _truncate_excerpt(str(passage.get("text") or ""))


class FakeModel:
    """A local prompt responder that only names stops found in supplied passages."""

    def __init__(self, request: dict[str, Any]):
        self.request = dict(request)
        self.passages: list[dict[str, Any]] = []
        self.costs: dict[str, Any] = {}

    def set_passages(
        self, passages: list[dict[str, Any]], primary_count: int | None = None
    ) -> None:
        self.passages = list(passages)
        self.primary_count = len(passages) if primary_count is None else primary_count

    def set_costs(self, costs: dict[str, Any]) -> None:
        self.costs = dict(costs)

    def __call__(self, prompt: str) -> str:
        if "Parse the user's trip request" in prompt:
            return json.dumps(self.request, ensure_ascii=False)
        return self._itinerary()

    def _itinerary(self) -> str:
        city = str(self.request["destination"])
        days = int(self.request["days"])
        style = str(self.request.get("style", "relaxed"))
        slots = TIME_SLOTS.get(style, TIME_SLOTS["relaxed"])
        start_date = self.request.get("start_date")
        start = date.fromisoformat(start_date) if start_date else None
        primary = _all_items(self.passages[:self.primary_count], city)
        target_per_day = len(slots)
        target_total = days * target_per_day
        items = list(primary)
        if len(items) < target_total:
            fallback = _all_items(
                self.passages[self.primary_count:], city, passage_offset=self.primary_count
            )
            for item in fallback:
                if not any(_names_overlap(item["name"], existing["name"]) for existing in items):
                    items.append(item)
        items = items[:target_total]
        day_rows = []
        stop_total = 0.0
        for day_number in range(1, days + 1):
            day_items = items[day_number - 1::days]
            stops = []
            for slot_index, item in enumerate(day_items):
                time_slot = slots[slot_index]
                passage = item["passage"]
                passage_index = item["passage_index"]
                description = item["description"]
                kind = kind_from_section(passage.get("section"))
                context = f"{item['name']} {description}".casefold()
                is_food = kind == "food"
                raw_cost = self.costs.get("meal_budget" if is_food else "typical_entry_fee_low")
                cost = float(raw_cost) if raw_cost is not None else 0.0
                stop_total += cost
                outdoor: bool | None = None
                if any(term in context for term in OUTDOOR_TERMS):
                    outdoor = True
                elif any(term in context for term in ("indoor", "museum", "gallery", "interior")):
                    outdoor = False
                stops.append({
                    "name": item["name"],
                    "area": _area_from_passage(description, city),
                    "time_slot": time_slot,
                    "duration_minutes": 60 if is_food else 90,
                    "est_cost_inr": cost,
                    "notes": "Offline sample based on the retrieved passage; verify current details.",
                    "outdoor": outdoor,
                    "passage_ids": [passage_index + 1],
                    "excerpt": _truncate_excerpt(description),
                    "kind": kind,
                })
            day_date = (start + timedelta(days=day_number - 1)).isoformat() if start else None
            day_rows.append({"day": day_number, "date": day_date, "stops": stops, "weather_note": None})
        assumptions = ["Offline sample; stop costs are estimates from the city cost table."]
        if len(items) < target_total:
            assumptions.append("Limited sample content for this destination.")
        return json.dumps({
            "city": city,
            "days": day_rows,
            "total_est_cost_inr": stop_total,
            "assumptions": assumptions,
        }, ensure_ascii=False)


def create_fake_model(request: dict[str, Any]) -> FakeModel:
    return FakeModel(request)
