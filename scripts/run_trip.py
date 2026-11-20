"""Run the trip planning graph from a terminal."""
from __future__ import annotations

import argparse
import json
import time
from datetime import date
from typing import Any, Callable

from backend.app.graph import nodes
from backend.app.graph.build import planning_graph
from backend.app.graph.state import TripState
from backend.app.llm import ask as real_ask


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan a city trip.")
    parser.add_argument("--city", required=True, choices=("Jaipur", "Chennai", "Goa"))
    parser.add_argument("--days", required=True, type=int)
    parser.add_argument("--budget", required=True, type=float, help="Total trip budget per person in INR")
    parser.add_argument("--interests", required=True, help="Comma-separated interests")
    parser.add_argument("--style", choices=("relaxed", "packed"), default="relaxed")
    parser.add_argument("--start-date", help="Optional start date (YYYY-MM-DD)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", dest="offline", action="store_true", help="Use the deterministic local model (default)")
    mode.add_argument("--live", dest="offline", action="store_false", help="Use the real model and spend model quota")
    parser.set_defaults(offline=True)
    parser.add_argument("--no-weather", action="store_true", help="Skip the optional weather lookup")
    return parser


def _fake_itinerary(city: str, days: int, passages: list[dict[str, Any]]) -> str:
    day_items = []
    for day_number in range(1, days + 1):
        passage = passages[(day_number - 1) % len(passages)] if passages else None
        stops = []
        if passage:
            section = str(passage.get("section") or "Guide stop").strip()
            name = section.split(" > ")[-1].strip() or "Guide stop"
            stops.append({
                "name": name,
                "area": city,
                "time_slot": "morning",
                "duration_minutes": 60,
                "est_cost_inr": 0,
                "notes": "Selected from a retrieved guide passage; check current details.",
                "outdoor": None,
                "passage_ids": [((day_number - 1) % len(passages)) + 1],
            })
        day_items.append({"day": day_number, "date": None, "stops": stops, "weather_note": None})
    return json.dumps({
        "city": city,
        "days": day_items,
        "total_est_cost_inr": 0,
        "assumptions": ["Stop costs are estimates; the model total is not used by the budget check."],
    })


def _print_result(
    state: dict[str, Any], elapsed: float, real_model_calls: int,
    output: Callable[..., Any] = print,
) -> None:
    draft = state.get("draft")
    if draft:
        for day in draft.get("days", []):
            date_text = f" ({day['date']})" if day.get("date") else ""
            output(f"Day {day.get('day')}{date_text}")
            if not day.get("stops"):
                output("  No stops found in retrieved passages.")
            for stop in day.get("stops", []):
                output(
                    f"  {stop.get('time_slot', 'time unknown')}: {stop.get('name', 'Unnamed stop')} "
                    f"— {stop.get('area', 'area unknown')} — INR {float(stop.get('est_cost_inr') or 0):.0f} estimated"
                )
                sources = stop.get("sources") or []
                for source in sources:
                    output(f"    Source: {source.get('source_name')} — {source.get('source_url')}")
                if stop.get("unverified"):
                    output("    UNVERIFIED")
    else:
        output("No itinerary was produced.")
    output("Costs are estimates.")
    for check in state.get("checks", []):
        label = "PASS" if check.get("passed") else "FAIL"
        output(f"{label} {check.get('name')}: {check.get('reason')}")
    output(f"Revisions: {state.get('revisions', 0)}")
    output(f"Real model calls: {real_model_calls}")
    unresolved = state.get("unresolved") or []
    output("Unresolved issues:")
    if unresolved:
        for reason in unresolved:
            output(f"  - {reason}")
    else:
        output("  None")
    output(f"Elapsed time: {elapsed:.2f} seconds")


def run_trip(
    args: argparse.Namespace,
    model_call: Callable[[str], str] | None = None,
    output: Callable[..., Any] = print,
) -> dict[str, Any]:
    request = {
        "destination": args.city,
        "days": args.days,
        "budget": args.budget,
        "interests": [item.strip() for item in args.interests.split(",") if item.strip()],
        "style": args.style,
        "start_date": args.start_date,
    }
    if not request["interests"]:
        raise ValueError("--interests must contain at least one item")

    retrieved: list[dict[str, Any]] = []
    original_retrieve = nodes.retrieve
    original_weather = nodes.get_weather
    original_ask = nodes.ask
    call_count = 0

    def collect_passages(city: str, query: str, k: int = 4) -> list[dict[str, Any]]:
        passages = original_retrieve(city, query, k)
        retrieved[:] = passages
        return passages

    def offline_model(prompt: str) -> str:
        if "Parse the user's trip request" in prompt:
            return json.dumps(request)
        return _fake_itinerary(args.city, args.days, retrieved)

    def counted_model(prompt: str) -> str:
        nonlocal call_count
        if args.offline:
            return offline_model(prompt)
        call_count += 1
        return (model_call or real_ask)(prompt)

    nodes.retrieve = collect_passages
    nodes.ask = counted_model
    if args.no_weather:
        nodes.get_weather = lambda city, start_date, days: {
            "available": False, "reason": "Weather lookup disabled by --no-weather.", "days": []
        }
    started = time.perf_counter()
    try:
        if not args.offline:
            output("Warning: live mode calls the real model and spends model quota.")
        initial_state: TripState = {
            "user_input": {"raw": f"{args.days} days in {args.city}; interests: {', '.join(request['interests'])}"},
            "request": None,
            "passages": [],
            "live_data": {},
            "draft": None,
            "feedback": [],
            "revisions": 0,
            "checks": [],
            "unresolved": [],
        }
        result = planning_graph.invoke(initial_state)
    finally:
        nodes.retrieve = original_retrieve
        nodes.get_weather = original_weather
        nodes.ask = original_ask
    elapsed = time.perf_counter() - started
    _print_result(result, elapsed, call_count, output)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.days < 1 or args.days > 7:
            parser.error("--days must be between 1 and 7")
        if args.budget <= 0:
            parser.error("--budget must be greater than 0")
        if args.start_date:
            date.fromisoformat(args.start_date)
        run_trip(args)
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
