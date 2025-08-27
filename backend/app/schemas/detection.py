from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.models.incident import IncidentSeverity


@dataclass(slots=True)
class DetectionFinding:
    """A single rule evaluation result that may become an incident."""

    rule_id: str
    fingerprint: str
    title: str
    severity: IncidentSeverity
    summary: str
    service_names: list[str] = field(default_factory=list)
    evidence: dict[str, object] = field(default_factory=dict)
    started_at: datetime | None = None


@dataclass(slots=True)
class DetectionRunResult:
    evaluated_at: datetime
    findings: list[DetectionFinding]
    created_incident_ids: list[UUID]
    skipped_fingerprints: list[str]
