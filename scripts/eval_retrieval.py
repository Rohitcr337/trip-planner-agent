"""Evaluate the local guide retriever against the Phase 2 question set."""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.retrieve import retrieve

DEFAULT_CASES_PATH = ROOT / "backend" / "tests" / "retrieval_cases.json"


def _cases_path(filename: str | None) -> Path:
    if not filename:
        return DEFAULT_CASES_PATH
    path = Path(filename)
    return path if path.is_absolute() else ROOT / "backend" / "tests" / path


def main(filename: str | None = None) -> None:
    cases = json.loads(_cases_path(filename).read_text(encoding="utf-8"))
    answerable = [case for case in cases if case.get("group", 1) != 3]
    evaluated: list[tuple[dict, list[dict], int | None]] = []
    misses: list[tuple[dict, list[dict]]] = []
    rejection_total = sum(case.get("group") == 3 for case in cases)
    rejection_hits = 0

    for case in cases:
        query = case.get("query", case.get("question", ""))
        results = retrieve(case["city"], query, k=4)
        if case.get("group") == 3:
            hit = not results
            rejection_hits += hit
            if not hit:
                misses.append((case, results))
            continue

        snippet = case["expected_snippet"]
        rank = next(
            (index for index, result in enumerate(results, start=1) if snippet in result["text"]),
            None,
        )
        evaluated.append((case, results, rank))
        if rank is None:
            misses.append((case, results))

    ranks = [rank for _, _, rank in evaluated]
    top4_hits = sum(rank is not None for rank in ranks)
    top1_hits = sum(rank == 1 for rank in ranks)

    print(f"Top-4 hit rate: {top4_hits}/{len(answerable)} ({top4_hits / len(answerable):.1%})")
    print(f"Top-1 hit rate: {top1_hits}/{len(answerable)} ({top1_hits / len(answerable):.1%})")
    mrr = sum(1 / rank for rank in ranks if rank is not None) / len(answerable)
    print(f"Mean reciprocal rank: {mrr:.3f}")
    for city in sorted({case["city"] for case in answerable}):
        city_ranks = [rank for case, _, rank in evaluated if case["city"] == city]
        city_top4 = sum(rank is not None for rank in city_ranks)
        city_top1 = sum(rank == 1 for rank in city_ranks)
        city_mrr = sum(1 / rank for rank in city_ranks if rank is not None) / len(city_ranks)
        print(
            f"{city}: top-4 {city_top4}/{len(city_ranks)} ({city_top4 / len(city_ranks):.1%}), "
            f"top-1 {city_top1}/{len(city_ranks)} ({city_top1 / len(city_ranks):.1%}), "
            f"MRR {city_mrr:.3f}"
        )
    print(f"Correctly rejected: {rejection_hits}/{rejection_total}")
    for case, results in misses:
        top_results = [result["text"][:120] for result in results]
        print(f"MISS: {case.get('query', case.get('question', ''))}")
        print(f"  expected: {case.get('expected_snippet', '(none; should reject)')}")
        print(f"  top results: {top_results}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
