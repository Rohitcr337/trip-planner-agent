"""
costs.py — load the hand-maintained per-city cost estimates.

data/costs.json holds estimated costs in INR. Values are filled in by hand;
null means "not filled in yet". load_costs(city) returns the city's values
plus a "complete" flag, and raises a clear error for an unknown city.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
COSTS_PATH = ROOT / "data" / "costs.json"

REQUIRED_FIELDS = (
    "meal_budget",
    "meal_mid",
    "local_transport_per_day",
    "typical_entry_fee_low",
    "typical_entry_fee_high",
    "stay_budget_per_night",
    "stay_mid_per_night",
)


def _load_file() -> dict[str, Any]:
    try:
        return json.loads(COSTS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Costs file not found at {COSTS_PATH}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read costs file at {COSTS_PATH}: {exc}") from exc


def load_costs(city: str) -> dict[str, Any]:
    """
    Return the estimated costs for one city plus "complete": bool.

    Raises ValueError for an unknown city or a city entry with missing fields.
    """
    data = _load_file()
    values = data.get(city)
    if not isinstance(values, dict):
        known = ", ".join(sorted(key for key in data if key != "note"))
        raise ValueError(f"Unknown city for costs: {city!r}. Known cities: {known}.")

    missing = [field for field in REQUIRED_FIELDS if field not in values]
    if missing:
        raise ValueError(f"Costs for {city!r} are missing fields: {', '.join(missing)}.")

    result = {field: values[field] for field in REQUIRED_FIELDS}
    result["complete"] = all(value is not None for value in result.values())
    return result
