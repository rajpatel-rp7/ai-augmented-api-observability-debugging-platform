from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.schemas.logs import LogDocument
from app.schemas.traces import SpanRead, TraceRead
from app.services.correlation import CorrelationService


def test_correlate_by_trace_id_joins_logs_and_spans() -> None:
    traces = MagicMock()
    logs = MagicMock()
    traces.get_trace.return_value = TraceRead(
        trace_id="a" * 32,
        services=["order-service", "payment-service"],
        span_count=2,
        duration_ms=150.0,
        spans=[
            SpanRead(
                span_id="1",
                service="order-service",
                operation="POST /orders",
                start_time=datetime.now(UTC),
                duration_ms=150.0,
                status="ok",
            )
        ],
    )
    logs.correlate.return_value = {
        "payment-service": [
            LogDocument(
                id="1",
                timestamp=datetime.now(UTC),
                service="payment-service",
                level="ERROR",
                message="database timeout",
                trace_id="a" * 32,
            )
        ]
    }

    result = CorrelationService(traces=traces, logs=logs).by_trace_id("a" * 32)
    assert result.span_count == 2
    assert result.log_count == 1
    assert result.affected_services == ["order-service", "payment-service"]
    assert "payment-service" in result.logs_by_service
