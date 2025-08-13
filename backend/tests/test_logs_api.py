from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.logs import get_log_service, get_stream_publisher
from app.main import app
from app.schemas.logs import LogDocument, LogSearchResult
from app.services.logs import LogServiceError


def test_ingest_and_search_endpoints(client: TestClient) -> None:
    logs = MagicMock()
    streams = MagicMock()
    logs.ingest.return_value = LogDocument(
        id="1",
        timestamp="2025-08-10T12:00:00Z",
        service="payment-service",
        level="ERROR",
        message="database timeout",
        trace_id="trace-1",
    )
    logs.search.return_value = LogSearchResult(total=1, items=[logs.ingest.return_value])
    logs.correlate.return_value = {"payment-service": [logs.ingest.return_value]}

    app.dependency_overrides[get_log_service] = lambda: logs
    app.dependency_overrides[get_stream_publisher] = lambda: streams
    try:
        created = client.post(
            "/api/v1/logs",
            json={
                "service": "payment-service",
                "level": "ERROR",
                "message": "database timeout",
                "trace_id": "trace-1",
            },
        )
        assert created.status_code == 201
        assert created.json()["service"] == "payment-service"
        streams.publish_log_event.assert_called_once()

        searched = client.get("/api/v1/logs/search", params={"trace_id": "trace-1"})
        assert searched.status_code == 200
        assert searched.json()["total"] == 1

        correlated = client.get("/api/v1/logs/correlate", params={"trace_id": "trace-1"})
        assert correlated.status_code == 200
        assert correlated.json()["total"] == 1
        assert "payment-service" in correlated.json()["services"]
    finally:
        app.dependency_overrides.pop(get_log_service, None)
        app.dependency_overrides.pop(get_stream_publisher, None)


def test_correlate_requires_filters(client: TestClient) -> None:
    logs = MagicMock()
    logs.correlate.side_effect = ValueError("Provide trace_id and/or service for correlation")
    app.dependency_overrides[get_log_service] = lambda: logs
    try:
        response = client.get("/api/v1/logs/correlate")
        assert response.status_code == 400
    finally:
        app.dependency_overrides.pop(get_log_service, None)


def test_search_returns_503_when_elasticsearch_unavailable(client: TestClient) -> None:
    logs = MagicMock()
    logs.search.side_effect = LogServiceError("Failed to search logs: down")
    app.dependency_overrides[get_log_service] = lambda: logs
    try:
        response = client.get("/api/v1/logs/search", params={"service": "payment-service"})
        assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_log_service, None)
