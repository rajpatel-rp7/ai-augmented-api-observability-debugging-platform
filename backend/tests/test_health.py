from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "service" in body


def test_root_returns_service_info() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "observability-platform"
    assert body["version"] == "0.9.0"
    assert body["docs"] == "/docs"
    assert body["ready"] == "/ready"


def test_ready_endpoint_shape() -> None:
    """Readiness may be 200 or 503 depending on whether Postgres is reachable."""
    response = client.get("/ready")
    assert response.status_code in {200, 503}
    body = response.json()
    assert body["status"] in {"ready", "unavailable"}
    assert "service" in body
    assert "database" in body
