from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_metrics_endpoint_exposes_prometheus_text() -> None:
    # Generate at least one instrumented request.
    assert client.get("/api/v1/services").status_code == 200

    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


def test_root_advertises_metrics_path() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["metrics"] == "/metrics"
