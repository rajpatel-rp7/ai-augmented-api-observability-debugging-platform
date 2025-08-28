from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.incident import IncidentRead
from app.services.detection import DetectionService

router = APIRouter(prefix="/detection", tags=["detection"])


class DetectionRuleInfo(BaseModel):
    rule_id: str
    description: str
    threshold: int | float | None = None
    threshold_ms: float | None = None
    window_minutes: int | None = None
    lookback_minutes: int | None = None


class DetectionFindingRead(BaseModel):
    rule_id: str
    fingerprint: str
    title: str
    severity: str
    summary: str
    service_names: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)


class DetectionRunResponse(BaseModel):
    evaluated_at: datetime
    findings: list[DetectionFindingRead]
    created_incidents: list[IncidentRead]
    skipped_fingerprints: list[str]


def get_detection_service() -> DetectionService:
    return DetectionService()


@router.get("/rules", response_model=list[DetectionRuleInfo])
def list_detection_rules(
    detection: DetectionService = Depends(get_detection_service),
) -> list[dict]:
    return detection.list_rules()


@router.post("/run", response_model=DetectionRunResponse)
def run_detection(
    db: Session = Depends(get_db),
    detection: DetectionService = Depends(get_detection_service),
) -> DetectionRunResponse:
    """Manually trigger a rule-based detection scan."""
    try:
        result = detection.run(db)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Detection run failed: {exc}",
        ) from exc

    created = detection.load_created_incidents(db, result.created_incident_ids)
    return DetectionRunResponse(
        evaluated_at=result.evaluated_at,
        findings=[
            DetectionFindingRead(
                rule_id=item.rule_id,
                fingerprint=item.fingerprint,
                title=item.title,
                severity=item.severity.value,
                summary=item.summary,
                service_names=item.service_names,
                evidence=item.evidence,
            )
            for item in result.findings
        ],
        created_incidents=created,
        skipped_fingerprints=result.skipped_fingerprints,
    )
