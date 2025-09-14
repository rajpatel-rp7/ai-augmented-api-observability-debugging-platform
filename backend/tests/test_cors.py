"""CORS middleware wiring."""

from fastapi.testclient import TestClient

from app.main import app


def test_cors_preflight_allows_dashboard_origin() -> None:
    client = TestClient(app)
    response = client.options(
        "/api/v1/incidents",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
