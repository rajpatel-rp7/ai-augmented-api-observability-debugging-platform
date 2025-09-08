from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.service import Service
from app.schemas.logs import LogDocument, LogSearchResult
from app.services.analysis import AnalysisService


def test_stub_analysis_for_timeout_errors(db_session: Session) -> None:
    service = Service(
        name="payment-service",
        display_name="Payment Service",
        environment="production",
    )
    db_session.add(service)
    db_session.flush()

    incident = Incident(
        title="Error spike detected on payment-service",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        summary="Multiple database timeout errors",
        detection_rule="error_log_spike",
        fingerprint="error_log_spike:payment-service",
        started_at=datetime.now(UTC),
        affected_services=[service],
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    logs = MagicMock()
    logs.search.return_value = LogSearchResult(
        total=1,
        items=[
            LogDocument(
                timestamp=datetime.now(UTC),
                service="payment-service",
                level="ERROR",
                message="database timeout",
            )
        ],
    )
    settings = Settings(openai_api_key=None, ai_analysis_force_stub=True)
    analysis = AnalysisService(logs=logs, settings=settings).analyze_incident(db_session, incident)

    assert analysis.provider == "stub"
    assert "connection" in analysis.root_cause.lower() or "timeout" in analysis.root_cause.lower()
    assert "payment-service" in analysis.affected_services
    assert len(analysis.recommendations) >= 3


def test_openai_path_parses_json_response(db_session: Session) -> None:
    service = Service(
        name="order-service",
        display_name="Order Service",
        environment="production",
    )
    db_session.add(service)
    db_session.flush()
    incident = Incident(
        title="Trace errors detected on order-service",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        detection_rule="trace_error",
        affected_services=[service],
        started_at=datetime.now(UTC),
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    logs = MagicMock()
    logs.search.return_value = LogSearchResult(total=0, items=[])

    openai_client = MagicMock()
    message = MagicMock()
    message.content = (
        '{"summary":"Order failures rising","root_cause":"Downstream payment failures",'
        '"affected_services":["order-service","payment-service"],'
        '"recommendations":["Check payment-service","Inspect traces"],'
        '"confidence":"high"}'
    )
    choice = MagicMock()
    choice.message = message
    openai_client.chat.completions.create.return_value = MagicMock(choices=[choice])

    settings = Settings(
        openai_api_key="test-key",
        openai_model="gpt-4o-mini",
        ai_analysis_force_stub=False,
    )
    analysis = AnalysisService(
        logs=logs,
        settings=settings,
        openai_client=openai_client,
    ).analyze_incident(db_session, incident)

    assert analysis.provider == "openai"
    assert analysis.model == "gpt-4o-mini"
    assert analysis.root_cause == "Downstream payment failures"
    assert analysis.confidence == "high"
    assert "Check payment-service" in analysis.recommendations
