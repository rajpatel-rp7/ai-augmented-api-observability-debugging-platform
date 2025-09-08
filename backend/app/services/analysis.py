from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.analysis import IncidentAnalysis
from app.models.incident import Incident
from app.schemas.analysis import IncidentAnalysisResult
from app.services.logs import LogService, LogServiceError

logger = logging.getLogger(__name__)


class AnalysisServiceError(RuntimeError):
    """Raised when incident analysis cannot be completed."""


class AnalysisService:
    """
    Produce incident summaries, likely root causes, and next steps.

    Uses OpenAI when configured; otherwise (or on failure) falls back to a
    deterministic heuristic stub so local demos remain useful.
    """

    def __init__(
        self,
        *,
        logs: LogService | None = None,
        settings: Settings | None = None,
        openai_client: OpenAI | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._logs = logs or LogService()
        self._openai = openai_client

    def analyze_incident(self, db: Session, incident: Incident) -> IncidentAnalysis:
        if not self._settings.ai_analysis_enabled:
            raise AnalysisServiceError("AI analysis is disabled")

        context = self._build_context(incident)
        result = self._generate(context)
        row = IncidentAnalysis(
            incident_id=incident.id,
            provider=result.provider,
            model=result.model,
            summary=result.summary,
            root_cause=result.root_cause,
            affected_services=result.affected_services,
            recommendations=result.recommendations,
            confidence=result.confidence,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def latest_for_incident(self, db: Session, incident_id) -> IncidentAnalysis | None:
        from sqlalchemy import select

        stmt = (
            select(IncidentAnalysis)
            .where(IncidentAnalysis.incident_id == incident_id)
            .order_by(IncidentAnalysis.created_at.desc())
            .limit(1)
        )
        return db.scalars(stmt).first()

    def _build_context(self, incident: Incident) -> dict[str, Any]:
        service_names = [svc.name for svc in incident.affected_services]
        sample_logs: list[dict[str, Any]] = []
        end = datetime.now(UTC)
        start = incident.started_at or (end - timedelta(minutes=30))
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)

        for name in service_names[:5]:
            try:
                result = self._logs.search(
                    service=name,
                    start=start,
                    end=end,
                    limit=10,
                )
            except LogServiceError:
                continue
            for item in result.items[:5]:
                sample_logs.append(
                    {
                        "service": item.service,
                        "level": item.level,
                        "message": item.message,
                        "trace_id": item.trace_id,
                    }
                )

        return {
            "title": incident.title,
            "severity": incident.severity.value if incident.severity else None,
            "status": incident.status.value if incident.status else None,
            "summary": incident.summary,
            "detection_rule": incident.detection_rule,
            "fingerprint": incident.fingerprint,
            "affected_services": service_names,
            "started_at": incident.started_at.isoformat() if incident.started_at else None,
            "sample_logs": sample_logs,
        }

    def _generate(self, context: dict[str, Any]) -> IncidentAnalysisResult:
        use_stub = (
            self._settings.ai_analysis_force_stub
            or not self._settings.openai_api_key
        )
        if not use_stub:
            try:
                return self._generate_openai(context)
            except Exception as exc:  # noqa: BLE001
                logger.warning("OpenAI analysis failed, using stub: %s", exc)
        return self._generate_stub(context)

    def _generate_openai(self, context: dict[str, Any]) -> IncidentAnalysisResult:
        client = self._openai or OpenAI(
            api_key=self._settings.openai_api_key,
            timeout=self._settings.openai_timeout_seconds,
        )
        system_prompt = (
            "You are an expert SRE analyzing production incidents. "
            "Return ONLY valid JSON with keys: summary (string), root_cause (string), "
            "affected_services (array of strings), recommendations (array of 3-5 short strings), "
            "confidence (low|medium|high)."
        )
        user_prompt = (
            "Analyze this incident context and suggest the most likely root cause "
            "and investigation steps.\n\n"
            f"{json.dumps(context, default=str)}"
        )
        response = client.chat.completions.create(
            model=self._settings.openai_model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return IncidentAnalysisResult(
            provider="openai",
            model=self._settings.openai_model,
            summary=str(payload.get("summary") or "Incident analysis unavailable."),
            root_cause=str(payload.get("root_cause") or "Unknown root cause."),
            affected_services=list(payload.get("affected_services") or context.get("affected_services") or []),
            recommendations=list(payload.get("recommendations") or []),
            confidence=str(payload.get("confidence") or "medium"),
        )

    def _generate_stub(self, context: dict[str, Any]) -> IncidentAnalysisResult:
        services = list(context.get("affected_services") or [])
        rule = context.get("detection_rule") or ""
        messages = " ".join(
            str(item.get("message", "")).lower()
            for item in (context.get("sample_logs") or [])
        )
        title = str(context.get("title") or "Incident")

        if "timeout" in messages or "timeout" in title.lower() or rule == "error_log_spike":
            root_cause = (
                "Likely database connection exhaustion or long-running queries "
                "causing upstream timeouts."
            )
            recommendations = [
                "Check database connection pool usage and saturation.",
                "Review slow-running queries around the incident window.",
                "Inspect recent deployments for schema or pool-size changes.",
                "Correlate ERROR logs with matching trace_ids in Jaeger.",
            ]
            confidence = "medium"
        elif rule == "high_latency":
            root_cause = (
                "Elevated end-to-end latency suggests a slow dependency or "
                "resource contention on the critical path."
            )
            recommendations = [
                "Inspect the slowest spans in recent traces for the affected service.",
                "Check CPU/memory and saturation on the service and its dependencies.",
                "Verify whether retries amplified load during the incident window.",
            ]
            confidence = "medium"
        elif rule == "trace_error":
            root_cause = (
                "Error spans indicate a failing dependency or unhandled exception "
                "on the request path."
            )
            recommendations = [
                "Open failing traces and identify the first error span.",
                "Review exception logs for the same trace_id.",
                "Check dependency health (DB, cache, downstream HTTP).",
            ]
            confidence = "medium"
        else:
            root_cause = (
                "Insufficient signal for a high-confidence root cause; "
                "treat this as an initial triage hypothesis."
            )
            recommendations = [
                "Review recent logs for the affected services.",
                "Compare latency and error rates before/after incident start.",
                "Check recent deployments and configuration changes.",
            ]
            confidence = "low"

        service_list = ", ".join(services) if services else "unknown services"
        summary = (
            f"{title}. Observed impact on {service_list}. "
            f"Detection rule: {rule or 'manual/unknown'}."
        )
        return IncidentAnalysisResult(
            provider="stub",
            model=None,
            summary=summary,
            root_cause=root_cause,
            affected_services=services,
            recommendations=recommendations,
            confidence=confidence,
        )
