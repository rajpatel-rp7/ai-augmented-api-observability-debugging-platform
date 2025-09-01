from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.service import Service
from app.schemas.detection import DetectionFinding
from app.schemas.logs import LogDocument, LogSearchResult
from app.schemas.traces import SpanRead, TraceRead, TraceSearchResult
from app.services.detection import DetectionService
from app.services.detection_rules import ErrorLogSpikeRule, TraceErrorRule, TraceLatencyRule


def _settings(**overrides) -> Settings:
    base = {
        "detection_error_log_threshold": 2,
        "detection_error_log_window_minutes": 5,
        "detection_trace_latency_ms": 1000.0,
        "detection_trace_error_threshold": 1,
        "detection_lookback_minutes": 15,
    }
    base.update(overrides)
    return Settings(**base)


def test_error_log_spike_rule_emits_finding() -> None:
    logs = MagicMock()
    logs.search.return_value = LogSearchResult(
        total=3,
        items=[
            LogDocument(
                timestamp=datetime.now(UTC),
                service="payment-service",
                level="ERROR",
                message="database timeout",
            )
        ],
    )
    service = Service(
        id=uuid4(),
        name="payment-service",
        display_name="Payment",
        environment="production",
    )
    findings = ErrorLogSpikeRule(logs=logs, settings=_settings()).evaluate([service])
    assert len(findings) == 1
    assert findings[0].rule_id == "error_log_spike"
    assert findings[0].fingerprint == "error_log_spike:payment-service"


def test_high_latency_rule_emits_finding() -> None:
    traces = MagicMock()
    traces.search.return_value = TraceSearchResult(
        total=1,
        items=[
            TraceRead(
                trace_id="a" * 32,
                services=["payment-service"],
                span_count=1,
                duration_ms=4200,
                spans=[],
            )
        ],
    )
    service = Service(
        id=uuid4(),
        name="payment-service",
        display_name="Payment",
        environment="production",
    )
    findings = TraceLatencyRule(traces=traces, settings=_settings()).evaluate([service])
    assert len(findings) == 1
    assert findings[0].rule_id == "high_latency"


def test_trace_error_rule_emits_finding() -> None:
    traces = MagicMock()
    traces.search.return_value = TraceSearchResult(
        total=1,
        items=[
            TraceRead(
                trace_id="a" * 32,
                services=["payment-service"],
                span_count=1,
                duration_ms=100,
                spans=[
                    SpanRead(
                        span_id="1",
                        service="payment-service",
                        operation="charge",
                        status="error",
                    )
                ],
            )
        ],
    )
    service = Service(
        id=uuid4(),
        name="payment-service",
        display_name="Payment",
        environment="production",
    )
    findings = TraceErrorRule(traces=traces, settings=_settings()).evaluate([service])
    assert len(findings) == 1
    assert findings[0].rule_id == "trace_error"


def test_detection_service_creates_and_deduplicates(db_session: Session) -> None:
    service = Service(
        name="payment-service",
        display_name="Payment Service",
        environment="production",
    )
    db_session.add(service)
    db_session.commit()

    finding = DetectionFinding(
        rule_id="error_log_spike",
        fingerprint="error_log_spike:payment-service",
        title="Error spike detected on payment-service",
        severity=IncidentSeverity.HIGH,
        summary="3 ERROR logs",
        service_names=["payment-service"],
        evidence={"error_count": 3},
    )

    class StubRule:
        rule_id = "error_log_spike"

        def evaluate(self, services):  # noqa: ANN001, ARG002
            return [finding]

    streams = MagicMock()
    detection = DetectionService(rules=[StubRule()], streams=streams, settings=_settings())

    first = detection.run(db_session)
    assert len(first.created_incident_ids) == 1
    streams.publish_incident_event.assert_called_once()

    second = detection.run(db_session)
    assert second.created_incident_ids == []
    assert "error_log_spike:payment-service" in second.skipped_fingerprints

    open_incidents = db_session.query(Incident).filter(Incident.status == IncidentStatus.OPEN).all()
    assert len(open_incidents) == 1
    assert open_incidents[0].fingerprint == "error_log_spike:payment-service"
    assert open_incidents[0].detection_rule == "error_log_spike"
