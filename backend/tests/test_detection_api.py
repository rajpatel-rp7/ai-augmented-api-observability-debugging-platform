from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.detection import get_detection_service
from app.main import app
from app.models.incident import IncidentSeverity
from app.schemas.detection import DetectionFinding, DetectionRunResult
from datetime import UTC, datetime


def test_list_detection_rules(client: TestClient) -> None:
    response = client.get("/api/v1/detection/rules")
    assert response.status_code == 200
    rule_ids = {item["rule_id"] for item in response.json()}
    assert rule_ids == {"error_log_spike", "high_latency", "trace_error"}


def test_run_detection_endpoint(client: TestClient) -> None:
    detection = MagicMock()
    incident_id = uuid4()
    detection.run.return_value = DetectionRunResult(
        evaluated_at=datetime.now(UTC),
        findings=[
            DetectionFinding(
                rule_id="error_log_spike",
                fingerprint="error_log_spike:payment-service",
                title="Error spike detected on payment-service",
                severity=IncidentSeverity.HIGH,
                summary="errors",
                service_names=["payment-service"],
            )
        ],
        created_incident_ids=[incident_id],
        skipped_fingerprints=[],
    )
    detection.load_created_incidents.return_value = []

    app.dependency_overrides[get_detection_service] = lambda: detection
    try:
        response = client.post("/api/v1/detection/run")
        assert response.status_code == 200
        body = response.json()
        assert len(body["findings"]) == 1
        assert body["findings"][0]["rule_id"] == "error_log_spike"
        detection.run.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_detection_service, None)
