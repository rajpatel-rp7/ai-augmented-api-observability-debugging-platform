from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.analysis import get_analysis_service
from app.main import app
from app.models.analysis import IncidentAnalysis


def test_analyze_incident_endpoint(client: TestClient, db_session) -> None:
    from app.models.incident import Incident, IncidentSeverity, IncidentStatus
    from app.models.service import Service

    service = Service(name="payment-service", display_name="Payment", environment="production")
    db_session.add(service)
    db_session.flush()
    incident = Incident(
        title="Payment Processing Failure",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        detection_rule="error_log_spike",
        affected_services=[service],
        started_at=datetime.now(UTC),
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    analysis_service = MagicMock()
    analysis_service.analyze_incident.return_value = IncidentAnalysis(
        id=uuid4(),
        incident_id=incident.id,
        provider="stub",
        model=None,
        summary="Payment failures observed",
        root_cause="Database connection exhaustion",
        affected_services=["payment-service"],
        recommendations=["Check pool usage", "Review slow queries"],
        confidence="medium",
        created_at=datetime.now(UTC),
    )

    app.dependency_overrides[get_analysis_service] = lambda: analysis_service
    try:
        response = client.post(f"/api/v1/incidents/{incident.id}/analyze")
        assert response.status_code == 201
        body = response.json()
        assert body["provider"] == "stub"
        assert body["root_cause"] == "Database connection exhaustion"
        analysis_service.analyze_incident.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_analysis_service, None)


def test_get_analysis_404_when_missing(client: TestClient, db_session) -> None:
    from app.models.incident import Incident, IncidentSeverity, IncidentStatus

    incident = Incident(
        title="Manual incident",
        severity=IncidentSeverity.LOW,
        status=IncidentStatus.OPEN,
        started_at=datetime.now(UTC),
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    response = client.get(f"/api/v1/incidents/{incident.id}/analysis")
    assert response.status_code == 404
