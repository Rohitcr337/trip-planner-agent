"""Run the trip planning graph from a terminal."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.graph import nodes
from backend.app.graph.build import planning_graph
from backend.app.graph.state import TripState
from backend.app.fake_model import create_fake_model
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
                if stop.get("excerpt"):
                    output(f"    Excerpt: {stop['excerpt']}")
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

    original_weather = nodes.get_weather
    original_ask = nodes.ask
    real_model_calls = 0
    fake_model = create_fake_model(request)

    def counted_model(prompt: str) -> str:
        nonlocal real_model_calls
        real_model_calls += 1
        return (model_call or real_ask)(prompt)

    if not args.offline:
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
            "fake_model": fake_model if args.offline else None,
        }
        result = planning_graph.invoke(initial_state)
    finally:
        nodes.get_weather = original_weather
        nodes.ask = original_ask
    elapsed = time.perf_counter() - started
    _print_result(result, elapsed, real_model_calls, output)
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
