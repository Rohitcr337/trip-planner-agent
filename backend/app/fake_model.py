"""Deterministic local itinerary samples grounded in retrieved passages."""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any


TIME_SLOTS = {
    "relaxed": ("morning", "afternoon", "evening"),
    "packed": ("morning", "afternoon", "evening", "evening"),
}
FOOD_TERMS = (
    "food", "restaurant", "cafe", "café", "cuisine", "meal", "eatery",
    "dining", "breakfast", "lunch", "dinner", "snack", "dish", "street food",
)
OUTDOOR_TERMS = ("beach", "fort", "garden", "hill", "waterfall", "park", "lake", "outdoor")


def _name_from_passage(passage: dict[str, Any]) -> str:
    section = str(passage.get("section") or "Guide passage").strip()
    heading = section.split(" > ")[-1].strip() or "Guide passage"
    text_words = re.findall(r"[\w’'-]+", str(passage.get("text") or ""))[:5]
    text_start = " ".join(text_words)
    name = f"{heading}: {text_start}" if text_start else heading
    name = re.sub(r"\s+", " ", name).strip(" :;,.—-")
    if len(name) > 76:
        name = name[:73].rsplit(" ", 1)[0] + "..."
    return name or "Guide passage"


def _area_from_passage(text: str, city: str) -> str:
    patterns = (
        r"\b(?:in|near|at|around|along|within)\s+([A-Z][A-Za-z’'-]*(?:\s+[A-Z][A-Za-z’'-]*){0,2})",
        r"\b(?:located|situated)\s+in\s+([A-Z][A-Za-z’'-]*(?:\s+[A-Z][A-Za-z’'-]*){0,2})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            area = match.group(1).strip(" ,.;:")
            if area.casefold() != city.casefold():
                return area
    return city


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
        stop_count = len(slots)
        start_date = self.request.get("start_date")
        start = date.fromisoformat(start_date) if start_date else None
        day_rows = []
        stop_total = 0.0
        for day_number in range(1, days + 1):
            stops = []
            for slot_index, time_slot in enumerate(slots):
                if not self.passages:
                    break
                passage_index = ((day_number - 1) * stop_count + slot_index) % len(self.passages)
                passage = self.passages[passage_index]
                description = f"{passage.get('section', '')} {passage.get('text', '')}".casefold()
                is_food = any(term in description for term in FOOD_TERMS)
                raw_cost = self.costs.get("meal_budget" if is_food else "typical_entry_fee_low")
                cost = float(raw_cost) if raw_cost is not None else 0.0
                stop_total += cost
                passage_text = str(passage.get("text") or "")
                outdoor: bool | None = None
                if any(term in description for term in OUTDOOR_TERMS):
                    outdoor = True
                elif any(term in description for term in ("indoor", "museum", "gallery", "interior")):
                    outdoor = False
                stops.append({
                    "name": _name_from_passage(passage),
                    "area": _area_from_passage(passage_text, city),
                    "time_slot": time_slot,
                    "duration_minutes": 60 if is_food else 90,
                    "est_cost_inr": cost,
                    "notes": "Offline sample based on the retrieved passage; verify current details.",
                    "outdoor": outdoor,
                    "passage_ids": [passage_index + 1],
                    "passage_text": passage_text,
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
