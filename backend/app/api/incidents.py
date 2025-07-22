from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.service import Service
from app.schemas.incident import IncidentCreate, IncidentRead, IncidentUpdate

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _load_incident(db: Session, incident_id: UUID) -> Incident | None:
    stmt = (
        select(Incident)
        .where(Incident.id == incident_id)
        .options(selectinload(Incident.affected_services))
    )
    return db.scalars(stmt).first()


def _resolve_services(db: Session, service_ids: list[UUID]) -> list[Service]:
    if not service_ids:
        return []
    services = list(db.scalars(select(Service).where(Service.id.in_(service_ids))).all())
    found_ids = {service.id for service in services}
    missing = [str(service_id) for service_id in service_ids if service_id not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown service ids: {', '.join(missing)}",
        )
    return services


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)) -> Incident:
    services = _resolve_services(db, payload.affected_service_ids)
    incident = Incident(
        title=payload.title,
        severity=payload.severity,
        status=payload.status,
        summary=payload.summary,
        started_at=payload.started_at or datetime.now(UTC),
        affected_services=services,
    )
    db.add(incident)
    db.commit()
    return _load_incident(db, incident.id)  # type: ignore[return-value]


@router.get("", response_model=list[IncidentRead])
def list_incidents(
    db: Session = Depends(get_db),
    status_filter: IncidentStatus | None = Query(default=None, alias="status"),
    severity: IncidentSeverity | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Incident]:
    stmt = (
        select(Incident)
        .options(selectinload(Incident.affected_services))
        .order_by(Incident.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if status_filter is not None:
        stmt = stmt.where(Incident.status == status_filter)
    if severity is not None:
        stmt = stmt.where(Incident.severity == severity)
    return list(db.scalars(stmt).all())


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: UUID, db: Session = Depends(get_db)) -> Incident:
    incident = _load_incident(db, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


@router.patch("/{incident_id}", response_model=IncidentRead)
def update_incident(
    incident_id: UUID,
    payload: IncidentUpdate,
    db: Session = Depends(get_db),
) -> Incident:
    incident = _load_incident(db, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    updates = payload.model_dump(exclude_unset=True)
    service_ids = updates.pop("affected_service_ids", None)

    for field, value in updates.items():
        setattr(incident, field, value)

    if payload.status == IncidentStatus.RESOLVED and incident.resolved_at is None:
        incident.resolved_at = datetime.now(UTC)

    if service_ids is not None:
        incident.affected_services = _resolve_services(db, service_ids)

    db.commit()
    refreshed = _load_incident(db, incident_id)
    assert refreshed is not None
    return refreshed


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_incident(incident_id: UUID, db: Session = Depends(get_db)) -> None:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    db.delete(incident)
    db.commit()
