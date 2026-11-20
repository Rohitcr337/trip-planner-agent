"""
Tests for the fetch node and its place in the graph — task 3.4.

All tools are mocked; no test makes a real network call.
"""
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.graph.build import build_graph
from backend.app.graph.nodes import fetch_node
from backend.app.graph.state import TripState
from backend.app.main import app

client = TestClient(app)

REQUEST = {
    "destination": "Jaipur",
    "days": 3,
    "budget": 8000,
    "interests": ["history"],
    "style": "relaxed",
    "start_date": "2026-12-01",
}

REQUEST_WITHOUT_DATE = {key: value for key, value in REQUEST.items() if key != "start_date"}

WEATHER = {
    "available": True,
    "reason": None,
    "days": [
        {
            "date": "2026-12-01",
            "temp_max_c": 28.0,
            "temp_min_c": 15.0,
            "precip_mm": 0.0,
            "rainy": False,
        }
    ],
}

COSTS = {
    "meal_budget": 100,
    "meal_mid": 300,
    "local_transport_per_day": 50,
    "typical_entry_fee_low": 20,
    "typical_entry_fee_high": 200,
    "stay_budget_per_night": 800,
    "stay_mid_per_night": 2500,
    "complete": True,
}


def _state(request: dict | None) -> TripState:
    return {
        "user_input": {},
        "request": request,
        "passages": [],
        "live_data": {},
        "draft": None,
        "feedback": [],
        "revisions": 0,
        "checks": [],
        "unresolved": [],
    }


class TestFetchNode:
    def test_writes_weather_costs_and_city(self):
        with patch("backend.app.graph.nodes.get_weather", return_value=WEATHER) as weather, patch(
            "backend.app.graph.nodes.load_costs", return_value=COSTS
        ) as costs:
            result = fetch_node(_state(REQUEST))

        weather.assert_called_once_with("Jaipur", "2026-12-01", 3)
        costs.assert_called_once_with("Jaipur")
        assert result["live_data"] == {"weather": WEATHER, "costs": COSTS, "city": "Jaipur"}
        assert result["request"] == REQUEST

    def test_without_start_date_skips_weather_but_loads_costs(self):
        with patch("backend.app.graph.nodes.get_weather") as weather, patch(
            "backend.app.graph.nodes.load_costs", return_value=COSTS
        ) as costs:
            result = fetch_node(_state(REQUEST_WITHOUT_DATE))

        weather.assert_not_called()
        costs.assert_called_once_with("Jaipur")
        assert result["live_data"]["weather"]["available"] is False
        assert "No start date" in result["live_data"]["weather"]["reason"]
        assert result["live_data"]["costs"] == COSTS

    def test_without_request_skips_everything(self):
        with patch("backend.app.graph.nodes.get_weather") as weather, patch(
            "backend.app.graph.nodes.load_costs"
        ) as costs:
            result = fetch_node(_state(None))

        weather.assert_not_called()
        costs.assert_not_called()
        assert result["live_data"] == {}

    def test_weather_exception_does_not_crash(self):
        with patch(
            "backend.app.graph.nodes.get_weather", side_effect=RuntimeError("boom")
        ), patch("backend.app.graph.nodes.load_costs", return_value=COSTS):
            result = fetch_node(_state(REQUEST))

        assert result["live_data"]["weather"]["available"] is False
        assert "boom" in result["live_data"]["weather"]["reason"]
        assert result["live_data"]["costs"] == COSTS

    def test_costs_exception_does_not_crash(self):
        with patch("backend.app.graph.nodes.get_weather", return_value=WEATHER), patch(
            "backend.app.graph.nodes.load_costs", side_effect=ValueError("no costs")
        ):
            result = fetch_node(_state(REQUEST))

        assert result["live_data"]["costs"]["available"] is False
        assert "no costs" in result["live_data"]["costs"]["reason"]
        assert result["live_data"]["weather"] == WEATHER


class TestGraphWithFetch:
    def test_graph_has_fetch_node(self):
        assert "fetch" in build_graph().nodes

    def test_graph_runs_fetch_after_retrieve(self):
        model_json = json.dumps(
            {
                "destination": "Jaipur",
                "days": 3,
                "budget": 8000,
                "interests": ["history"],
                "style": "relaxed",
                "start_date": "2026-12-01",
            }
        )
        with patch("backend.app.graph.nodes.ask", return_value=model_json), patch(
            "backend.app.graph.nodes.retrieve", return_value=[]
        ), patch(
            "backend.app.graph.nodes.get_weather", return_value=WEATHER
        ), patch(
            "backend.app.graph.nodes.load_costs", return_value=COSTS
        ):
            result = build_graph().invoke(
                _state(None) | {"user_input": {"raw": "Jaipur, 3 days, from 2026-12-01"}}
            )

        assert result["request"]["start_date"] == "2026-12-01"
        assert result["live_data"] == {"weather": WEATHER, "costs": COSTS, "city": "Jaipur"}


class TestIntakeEndpointStillWorks:
    def _post(self, raw: str):
        return client.post("/plan/intake", json={"user_input": {"raw": raw}})

    def test_intake_with_start_date_returns_200(self):
        model_json = json.dumps(
            {
                "destination": "Goa",
                "days": 2,
                "budget": 6000,
                "interests": ["beach"],
                "style": "relaxed",
                "start_date": "2026-12-05",
            }
        )
        with patch("backend.app.graph.nodes.ask", return_value=model_json), patch(
            "backend.app.graph.nodes.retrieve", return_value=[]
        ), patch(
            "backend.app.graph.nodes.get_weather", return_value=WEATHER
        ) as weather, patch(
            "backend.app.graph.nodes.load_costs", return_value=COSTS
        ):
            response = self._post("Goa, 2 days, from 2026-12-05")

        assert response.status_code == 200
        assert response.json()["request"]["start_date"] == "2026-12-05"
        weather.assert_called_once_with("Goa", "2026-12-05", 2)

    def test_intake_without_start_date_still_responds(self):
        model_json = json.dumps(
            {
                "destination": "Chennai",
                "days": 2,
                "budget": 6000,
                "interests": ["temples"],
                "style": "packed",
            }
        )
        with patch("backend.app.graph.nodes.ask", return_value=model_json), patch(
            "backend.app.graph.nodes.retrieve", return_value=[]
        ), patch("backend.app.graph.nodes.get_weather") as weather, patch(
            "backend.app.graph.nodes.load_costs", return_value=COSTS
        ):
            response = self._post("Chennai, 2 days")

        assert response.status_code == 200
        assert response.json()["request"]["destination"] == "Chennai"
        weather.assert_not_called()
