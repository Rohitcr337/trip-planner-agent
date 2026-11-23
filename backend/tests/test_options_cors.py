import importlib

from fastapi.testclient import TestClient

import backend.app.main as main_module


def _client_with_origins(monkeypatch, origins=None):
    if origins is None:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("CORS_ORIGINS", origins)
    refreshed = importlib.reload(main_module)
    return TestClient(refreshed.app)


def _preflight(client, origin):
    return client.options(
        "/plan",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_options_returns_form_values():
    response = TestClient(main_module.app).get("/options")
    assert response.status_code == 200
    data = response.json()
    assert data["cities"] == ["Jaipur", "Chennai", "Goa"]
    assert data["destinations"] == [
        {"name": "Jaipur", "lat": 26.9124, "lon": 75.7873},
        {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
        {"name": "Goa", "lat": 15.4909, "lon": 73.8278},
    ]
    assert data["styles"] == ["relaxed", "packed"]
    assert data["day_range"] == {"min": 1, "max": 7}
    assert "history" in data["interest_suggestions"]


def test_cors_defaults_allow_both_local_frontend_origins(monkeypatch):
    client = _client_with_origins(monkeypatch)
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        response = _preflight(client, origin)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_cors_preflight_allows_the_authorization_header(monkeypatch):
    client = _client_with_origins(monkeypatch)
    response = client.options(
        "/plan",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert response.status_code == 200
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed
    assert "content-type" in allowed


def test_cors_environment_value_replaces_defaults(monkeypatch):
    client = _client_with_origins(monkeypatch, "https://frontend.example, https://preview.example")
    allowed = _preflight(client, "https://frontend.example")
    blocked = _preflight(client, "http://localhost:5173")
    assert allowed.headers["access-control-allow-origin"] == "https://frontend.example"
    assert "access-control-allow-origin" not in blocked.headers
