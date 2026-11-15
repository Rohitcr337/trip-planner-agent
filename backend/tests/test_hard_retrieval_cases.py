import json
from pathlib import Path


def test_hard_retrieval_case_set_has_three_groups():
    cases = json.loads(
        (Path(__file__).parent / "retrieval_cases_hard.json").read_text(
            encoding="utf-8"
        )
    )

    assert len(cases) == 20
    assert {case["group"] for case in cases} == {1, 2, 3}
    assert sum(case["group"] == 3 for case in cases) == 5
    assert all(
        "expected_snippet" in case and 1 <= len(case["expected_snippet"].split()) <= 10
        for case in cases
        if case["group"] != 3
    )
    assert all("expected_snippet" not in case for case in cases if case["group"] == 3)
