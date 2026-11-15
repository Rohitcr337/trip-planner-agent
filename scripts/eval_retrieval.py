"""Evaluate the local guide retriever against the Phase 2 question set."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.retrieve import retrieve

CASES_PATH = ROOT / "backend" / "tests" / "retrieval_cases.json"


def main() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    hits = 0
    by_city: dict[str, list[bool]] = {}
    misses: list[tuple[dict, list[dict]]] = []

    for case in cases:
        results = retrieve(case["city"], case["question"], k=4)
        hit = any(case["expected_snippet"] in result["text"] for result in results)
        hits += hit
        by_city.setdefault(case["city"], []).append(hit)
        if not hit:
            misses.append((case, results))

    print(f"Overall hit rate: {hits}/{len(cases)} ({hits / len(cases):.1%})")
    for city, city_results in sorted(by_city.items()):
        city_hits = sum(city_results)
        print(
            f"{city} hit rate: {city_hits}/{len(city_results)} "
            f"({city_hits / len(city_results):.1%})"
        )
    for case, results in misses:
        top_results = [result["text"][:120] for result in results]
        print(f"MISS: {case['question']}")
        print(f"  expected: {case['expected_snippet']}")
        print(f"  top results: {top_results}")


if __name__ == "__main__":
    main()
