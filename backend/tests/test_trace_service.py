from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.schemas.traces import SpanIngest, TraceIngest
from app.services.traces import TraceService, TraceServiceError


@pytest.fixture()
def jaeger_client() -> MagicMock:
    return MagicMock()


def test_ingest_converts_to_zipkin_and_posts(jaeger_client: MagicMock) -> None:
    service = TraceService(client=jaeger_client)
    payload = TraceIngest(
        trace_id="abc123",
        spans=[
            SpanIngest(
                span_id="1",
                service="order-service",
                operation="POST /orders",
                start_time=datetime(2025, 8, 18, 12, 0, tzinfo=UTC),
                duration_ms=25.5,
                status="ok",
            ),
            SpanIngest(
                span_id="2",
                parent_span_id="1",
                service="payment-service",
                operation="charge",
                start_time=datetime(2025, 8, 18, 12, 0, 0, 100000, tzinfo=UTC),
                duration_ms=4200,
                status="error",
                tags={"db.system": "postgres"},
            ),
        ],
    )

    result = service.ingest(payload)
    assert result.span_count == 2
    assert len(result.trace_id) == 32
    jaeger_client.ingest_zipkin_spans.assert_called_once()
    spans = jaeger_client.ingest_zipkin_spans.call_args.args[0]
    assert spans[0]["localEndpoint"]["serviceName"] == "order-service"
    assert spans[1]["parentId"] == "0000000000000001"
    assert spans[1]["tags"]["error"] == "true"


def test_get_trace_parses_jaeger_payload(jaeger_client: MagicMock) -> None:
    jaeger_client.get_trace.return_value = {
        "traceID": "a" * 32,
        "processes": {"p1": {"serviceName": "payment-service"}},
        "spans": [
            {
                "traceID": "a" * 32,
                "spanID": "b" * 16,
                "operationName": "charge",
                "startTime": 1_724_000_000_000_000,
                "duration": 4_200_000,
                "processID": "p1",
                "tags": [{"key": "error", "value": True}],
                "references": [],
            }
        ],
    }
    service = TraceService(client=jaeger_client)
    trace = service.get_trace("a" * 32)
    assert trace is not None
    assert trace.services == ["payment-service"]
    assert trace.span_count == 1
    assert trace.spans[0].status == "error"
    assert trace.duration_ms == 4200.0


def test_search_requires_service(jaeger_client: MagicMock) -> None:
    service = TraceService(client=jaeger_client)
    with pytest.raises(ValueError):
        service.search(service=None)  # type: ignore[arg-type]


def test_get_trace_wraps_client_errors(jaeger_client: MagicMock) -> None:
    from app.clients.jaeger import JaegerClientError

    jaeger_client.get_trace.side_effect = JaegerClientError("down")
    service = TraceService(client=jaeger_client)
    with pytest.raises(TraceServiceError):
        service.get_trace("a" * 32)
