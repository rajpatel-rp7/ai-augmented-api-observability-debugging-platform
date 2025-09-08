from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IncidentAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    provider: str
    model: str | None = None
    summary: str
    root_cause: str
    affected_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: str
    created_at: datetime


class IncidentAnalysisResult(BaseModel):
    """In-memory analysis payload before persistence."""

    provider: str
    model: str | None = None
    summary: str
    root_cause: str
    affected_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: str = "medium"
