from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.analysis import IncidentAnalysis
from app.models.incident import Incident
from app.schemas.analysis import IncidentAnalysisRead
from app.services.analysis import AnalysisService, AnalysisServiceError

router = APIRouter(prefix="/incidents", tags=["analysis"])


def get_analysis_service() -> AnalysisService:
    return AnalysisService()


def _load_incident(db: Session, incident_id: UUID) -> Incident | None:
    stmt = (
        select(Incident)
        .where(Incident.id == incident_id)
        .options(selectinload(Incident.affected_services))
    )
    return db.scalars(stmt).first()


@router.post(
    "/{incident_id}/analyze",
    response_model=IncidentAnalysisRead,
    status_code=status.HTTP_201_CREATED,
)
def analyze_incident(
    incident_id: UUID,
    db: Session = Depends(get_db),
    analysis: AnalysisService = Depends(get_analysis_service),
) -> IncidentAnalysis:
    """Run AI-assisted (or stub) analysis for an incident."""
    incident = _load_incident(db, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    try:
        return analysis.analyze_incident(db, incident)
    except AnalysisServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/{incident_id}/analysis", response_model=IncidentAnalysisRead)
def get_latest_analysis(
    incident_id: UUID,
    db: Session = Depends(get_db),
) -> IncidentAnalysis:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    stmt = (
        select(IncidentAnalysis)
        .where(IncidentAnalysis.incident_id == incident_id)
        .order_by(IncidentAnalysis.created_at.desc())
        .limit(1)
    )
    row = db.scalars(stmt).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No analysis found")
    return row


@router.get("/{incident_id}/analyses", response_model=list[IncidentAnalysisRead])
def list_analyses(
    incident_id: UUID,
    db: Session = Depends(get_db),
) -> list[IncidentAnalysis]:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    stmt = (
        select(IncidentAnalysis)
        .where(IncidentAnalysis.incident_id == incident_id)
        .order_by(IncidentAnalysis.created_at.desc())
    )
    return list(db.scalars(stmt).all())
