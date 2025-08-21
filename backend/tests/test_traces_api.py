from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.correlation import get_correlation_service
from app.api.traces import get_trace_service
from app.main import app
from app.schemas.traces import TraceIngestResult, TraceRead, TraceSearchResult
from app.services.correlation import TraceCorrelationResult
from app.services.traces import TraceServiceError


def test_trace_ingest_and_get_endpoints(client: TestClient) -> None:
    traces = MagicMock()
    traces.ingest.return_value = TraceIngestResult(trace_id="a" * 32, span_count=2)
    traces.get_trace.return_value = TraceRead(
        trace_id="a" * 32,
        services=["payment-service"],
        span_count=2,
        duration_ms=42.0,
        spans=[],
    )
    app.dependency_overrides[get_trace_service] = lambda: traces
    try:
        created = client.post(
            "/api/v1/traces",
            json={
                "trace_id": "abc123",
                "spans": [
                    {
                        "span_id": "1",
                        "service": "payment-service",
                        "operation": "charge",
                        "start_time": datetime.now(UTC).isoformat(),
                        "duration_ms": 42,
                        "status": "ok",
                    }
                ],
            },
        )
        assert created.status_code == 202

        fetched = client.get(f"/api/v1/traces/{'a' * 32}")
        assert fetched.status_code == 200
        assert fetched.json()["trace_id"] == "a" * 32
    finally:
        app.dependency_overrides.pop(get_trace_service, None)


def test_trace_search_endpoint(client: TestClient) -> None:
    traces = MagicMock()
    traces.search.return_value = TraceSearchResult(total=0, items=[])
    app.dependency_overrides[get_trace_service] = lambda: traces
    try:
        response = client.get("/api/v1/traces/search", params={"service": "payment-service"})
        assert response.status_code == 200
        assert response.json()["total"] == 0
    finally:
        app.dependency_overrides.pop(get_trace_service, None)


def test_trace_get_returns_503_when_jaeger_down(client: TestClient) -> None:
    traces = MagicMock()
    traces.get_trace.side_effect = TraceServiceError("Failed to fetch trace: down")
    app.dependency_overrides[get_trace_service] = lambda: traces
    try:
        response = client.get(f"/api/v1/traces/{'a' * 32}")
        assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_trace_service, None)


def test_correlate_trace_endpoint(client: TestClient) -> None:
    correlation = MagicMock()
    correlation.by_trace_id.return_value = TraceCorrelationResult(
        trace_id="a" * 32,
        trace=TraceRead(trace_id="a" * 32, services=["payment-service"], span_count=1),
        logs_by_service={},
        affected_services=["payment-service"],
        log_count=0,
        span_count=1,
    )
    app.dependency_overrides[get_correlation_service] = lambda: correlation
    try:
        response = client.get(f"/api/v1/correlate/trace/{'a' * 32}")
        assert response.status_code == 200
        assert response.json()["span_count"] == 1
    finally:
        app.dependency_overrides.pop(get_correlation_service, None)
