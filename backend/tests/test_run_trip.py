import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from scripts.run_trip import build_parser, run_trip

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_SCRIPT = PROJECT_ROOT / "scripts" / "run_trip.py"


PASSAGE = {
    "text": "Amber Fort is a historic fort in Amer.",
    "section": "Amber Fort",
    "source_name": "Jaipur Guide",
    "source_url": "https://example.test/jaipur",
}
COSTS = {
    "complete": True, "meal_budget": 100, "meal_mid": 100,
    "local_transport_per_day": 50, "typical_entry_fee_low": 10,
    "typical_entry_fee_high": 20, "stay_budget_per_night": 500,
    "stay_mid_per_night": 500,
}


def test_arguments_default_to_offline_and_parse_trip_options():
    args = build_parser().parse_args([
        "--city", "Jaipur", "--days", "2", "--budget", "5000",
        "--interests", "history, food", "--style", "packed", "--start-date", "2026-12-01",
    ])
    assert args.offline is True
    assert args.city == "Jaipur"
    assert args.days == 2
    assert args.interests == "history, food"
    assert args.style == "packed"
    assert args.start_date == "2026-12-01"


def test_script_help_works_from_another_working_directory(tmp_path):
    result = subprocess.run(
        [sys.executable, str(RUN_SCRIPT), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()


def test_offline_run_uses_retrieved_stops_and_makes_no_model_or_http_calls():
    args = build_parser().parse_args([
        "--city", "Jaipur", "--days", "1", "--budget", "5000",
        "--interests", "history", "--no-weather",
    ])
    lines = []
    with patch("backend.app.graph.nodes.retrieve", return_value=[PASSAGE]), \
         patch("backend.app.graph.nodes.load_costs", return_value=COSTS), \
         patch("backend.app.graph.nodes.geocode", return_value=None), \
         patch("backend.app.checks.get_distance", side_effect=AssertionError("unexpected distance call")), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")), \
         patch("scripts.run_trip.real_ask", side_effect=AssertionError("unexpected model call")):
        result = run_trip(args, output=lines.append)

    assert result["draft"]["days"][0]["stops"][0]["name"] == "Amber Fort"
    assert result["draft"]["days"][0]["stops"][0]["sources"][0]["source_name"] == "Jaipur Guide"
    assert result["revisions"] == 0
    assert all(item["passed"] for item in result["checks"])
    assert "Costs are estimates." in lines
    assert any("Real model calls: 0" in line for line in lines)
    assert any("PASS budget" in line for line in lines)


def test_offline_fake_also_handles_revision_prompts():
    args = build_parser().parse_args([
        "--city", "Goa", "--days", "1", "--budget", "1",
        "--interests", "beach", "--no-weather",
    ])
    with patch("backend.app.graph.nodes.retrieve", return_value=[PASSAGE]), \
         patch("backend.app.graph.nodes.load_costs", return_value=COSTS), \
         patch("backend.app.graph.nodes.geocode", return_value=None), \
         patch("backend.app.tools.httpx.get", side_effect=AssertionError("unexpected HTTP call")), \
         patch("scripts.run_trip.real_ask", side_effect=AssertionError("unexpected model call")):
        result = run_trip(args, output=lambda line: None)
    assert result["revisions"] == 3
    assert result["draft"]["days"][0]["stops"][0]["name"] == "Amber Fort"
    assert result["unresolved"]
