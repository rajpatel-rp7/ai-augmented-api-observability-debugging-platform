from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.incident import IncidentSeverity, IncidentStatus
from app.schemas.service import ServiceRead


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    status: IncidentStatus = IncidentStatus.OPEN
    summary: str | None = None
    started_at: datetime | None = None
    affected_service_ids: list[UUID] = Field(default_factory=list)


class IncidentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    severity: IncidentSeverity | None = None
    status: IncidentStatus | None = None
    summary: str | None = None
    resolved_at: datetime | None = None
    affected_service_ids: list[UUID] | None = None


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: IncidentStatus
    severity: IncidentSeverity
    summary: str | None
    fingerprint: str | None = None
    detection_rule: str | None = None
    started_at: datetime
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    affected_services: list[ServiceRead] = Field(default_factory=list)
