from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.models.incident import Incident, IncidentStatus
from app.models.service import Service
from app.schemas.detection import DetectionFinding, DetectionRunResult
from app.services.detection_rules import (
    DetectionRule,
    ErrorLogSpikeRule,
    TraceErrorRule,
    TraceLatencyRule,
)
from app.services.streams import StreamPublisher, StreamServiceError

logger = logging.getLogger(__name__)


class DetectionService:
    """Evaluate detection rules and create deduplicated incidents."""

    def __init__(
        self,
        *,
        rules: list[DetectionRule] | None = None,
        streams: StreamPublisher | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._streams = streams or StreamPublisher()
        self._rules = rules or [
            ErrorLogSpikeRule(settings=self._settings),
            TraceLatencyRule(settings=self._settings),
            TraceErrorRule(settings=self._settings),
        ]

    def list_rules(self) -> list[dict[str, object]]:
        return [
            {
                "rule_id": "error_log_spike",
                "description": "ERROR log count exceeds threshold in a short window",
                "threshold": self._settings.detection_error_log_threshold,
                "window_minutes": self._settings.detection_error_log_window_minutes,
            },
            {
                "rule_id": "high_latency",
                "description": "Recent traces exceed latency threshold",
                "threshold_ms": self._settings.detection_trace_latency_ms,
                "lookback_minutes": self._settings.detection_lookback_minutes,
            },
            {
                "rule_id": "trace_error",
                "description": "Recent traces contain error spans",
                "threshold": self._settings.detection_trace_error_threshold,
                "lookback_minutes": self._settings.detection_lookback_minutes,
            },
        ]

    def run(self, db: Session) -> DetectionRunResult:
        services = list(db.scalars(select(Service).order_by(Service.name)).all())
        findings: list[DetectionFinding] = []
        for rule in self._rules:
            try:
                findings.extend(rule.evaluate(services))
            except Exception:  # noqa: BLE001 - one bad rule should not abort the scan
                logger.exception("Detection rule %s failed", getattr(rule, "rule_id", rule))

        created_ids: list[UUID] = []
        skipped: list[str] = []

        for finding in findings:
            if self._has_open_incident(db, finding.fingerprint):
                skipped.append(finding.fingerprint)
                continue
            incident = self._create_incident(db, finding, services)
            created_ids.append(incident.id)
            self._publish_event(incident, finding)

        db.commit()
        return DetectionRunResult(
            evaluated_at=datetime.now(UTC),
            findings=findings,
            created_incident_ids=created_ids,
            skipped_fingerprints=skipped,
        )

    def _has_open_incident(self, db: Session, fingerprint: str) -> bool:
        stmt = (
            select(Incident.id)
            .where(
                Incident.fingerprint == fingerprint,
                Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.INVESTIGATING]),
            )
            .limit(1)
        )
        return db.scalars(stmt).first() is not None

    def _create_incident(
        self,
        db: Session,
        finding: DetectionFinding,
        services: list[Service],
    ) -> Incident:
        by_name = {service.name: service for service in services}
        affected = [by_name[name] for name in finding.service_names if name in by_name]
        incident = Incident(
            title=finding.title,
            severity=finding.severity,
            status=IncidentStatus.OPEN,
            summary=finding.summary,
            fingerprint=finding.fingerprint,
            detection_rule=finding.rule_id,
            started_at=finding.started_at or datetime.now(UTC),
            affected_services=affected,
        )
        db.add(incident)
        db.flush()
        db.refresh(incident)
        # Ensure relationship is loaded for event payload.
        _ = incident.id
        return incident

    def _publish_event(self, incident: Incident, finding: DetectionFinding) -> None:
        payload = {
            "event": "incident.detected",
            "incident_id": str(incident.id),
            "fingerprint": finding.fingerprint,
            "rule_id": finding.rule_id,
            "title": finding.title,
            "severity": finding.severity.value,
            "service_names": finding.service_names,
            "evidence": finding.evidence,
        }
        try:
            self._streams.publish_incident_event(payload)
        except StreamServiceError as exc:
            logger.warning("Failed to publish incident event: %s", exc)

    def load_created_incidents(self, db: Session, incident_ids: list[UUID]) -> list[Incident]:
        if not incident_ids:
            return []
        stmt = (
            select(Incident)
            .where(Incident.id.in_(incident_ids))
            .options(selectinload(Incident.affected_services))
        )
        return list(db.scalars(stmt).all())
