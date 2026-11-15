import json
from pathlib import Path


def test_retrieval_case_set_has_twenty_questions():
    cases_path = Path(__file__).with_name("retrieval_cases.json")
    cases = json.loads(cases_path.read_text(encoding="utf-8"))

    assert len(cases) == 20
    assert {case["city"] for case in cases} == {"Jaipur", "Chennai", "Goa"}
    assert all(1 <= len(case["expected_snippet"].split()) <= 10 for case in cases)
