"""Deterministic local itinerary samples grounded in retrieved passages."""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

from backend.app.text import clean_text


TIME_SLOTS = {
    "relaxed": ("morning", "afternoon", "evening"),
    "packed": ("morning", "afternoon", "evening", "evening"),
}
FOOD_TERMS = (
    "food", "restaurant", "cafe", "café", "cuisine", "meal", "eatery",
    "dining", "breakfast", "lunch", "dinner", "snack", "dish", "street food",
)
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
_DISTRICT_PATTERNS = (
    re.compile(r"\b(?:North|South)\s+Goa\b", re.IGNORECASE),
    re.compile(r"\bBardez\b", re.IGNORECASE),
    re.compile(
        r"\b([A-Z][A-Za-z'’.-]*(?:\s+[A-Z][A-Za-z'’.-]*){0,2})\s+(?:district|taluka)\b",
        re.IGNORECASE,
    ),
)


def _valid_name(value: str, city: str) -> str | None:
    name = clean_text(value).strip(" \t\r\n:;,.—–-_'\"()[]{}")
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    words = name.split()
    while len(words) > 1 and words[0].casefold() in {"a", "an", "the", "at", "in"}:
        words.pop(0)
    name = " ".join(words)
    words = name.split()
    if not 1 <= len(words) <= 5 or name.casefold() == city.casefold():
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
        items.append({
            "name": name,
            "description": _truncate_excerpt(sentence),
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
    for segment in _LIST_ITEM.split(text):
        if "—" not in segment:
            continue
        raw_name, raw_description = segment.split("—", 1)
        name = _valid_name(raw_name, city)
        description = clean_text(raw_description).strip(" —–-:;,.\t")
        if name:
            items.append({
                "name": name,
                "description": description,
                "passage_index": passage_index,
                "passage": passage,
            })
    if not items:
        items = _fallback_candidates(text, city, passage_index, passage)
    return items


def _all_items(passages: list[dict[str, Any]], city: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for passage_index, passage in enumerate(passages):
        for item in _passage_items(passage, passage_index, city):
            key = item["name"].casefold()
            if key not in seen:
                items.append(item)
                seen.add(key)
    return items


def _area_from_passage(text: str, city: str) -> str:
    text = clean_text(text)
    for pattern in _DISTRICT_PATTERNS:
        match = pattern.search(text)
        if match:
            return clean_text(match.group(1) if match.lastindex else match.group(0))
    return city


def _truncate_excerpt(value: str, maximum: int = 200) -> str:
    text = clean_text(value)
    if len(text) <= maximum:
        return text
    prefix = text[:maximum]
    if " " not in prefix:
        return ""
    return prefix.rsplit(" ", 1)[0].rstrip(" ,;:-")


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

    def set_passages(self, passages: list[dict[str, Any]]) -> None:
        self.passages = list(passages)

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
        items = _all_items(self.passages, city)
        day_rows = []
        stop_total = 0.0
        item_cursor = 0
        for day_number in range(1, days + 1):
            stops = []
            for slot_index, time_slot in enumerate(slots):
                if item_cursor >= len(items):
                    break
                item = items[item_cursor]
                item_cursor += 1
                passage = item["passage"]
                passage_index = item["passage_index"]
                description = item["description"]
                context = f"{passage.get('section', '')} {item['name']} {description}".casefold()
                is_food = any(term in context for term in FOOD_TERMS)
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
                })
            day_date = (start + timedelta(days=day_number - 1)).isoformat() if start else None
            day_rows.append({"day": day_number, "date": day_date, "stops": stops, "weather_note": None})
        return json.dumps({
            "city": city,
            "days": day_rows,
            "total_est_cost_inr": stop_total,
            "assumptions": ["Offline sample; stop costs are estimates from the city cost table."],
        }, ensure_ascii=False)


def create_fake_model(request: dict[str, Any]) -> FakeModel:
    return FakeModel(request)
