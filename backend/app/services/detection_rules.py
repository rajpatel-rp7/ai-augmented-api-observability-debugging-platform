"""Rule-based anomaly detectors used by the detection engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.core.config import Settings, get_settings
from app.models.incident import IncidentSeverity
from app.models.service import Service
from app.schemas.detection import DetectionFinding
from app.services.logs import LogService, LogServiceError
from app.services.traces import TraceService, TraceServiceError


class DetectionRule(Protocol):
    rule_id: str

    def evaluate(self, services: list[Service]) -> list[DetectionFinding]:
        ...


class ErrorLogSpikeRule:
    """Fire when ERROR logs for a service exceed a threshold in a short window."""

    rule_id = "error_log_spike"

    def __init__(
        self,
        *,
        logs: LogService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._logs = logs or LogService()
        self._settings = settings or get_settings()

    def evaluate(self, services: list[Service]) -> list[DetectionFinding]:
        window = timedelta(minutes=self._settings.detection_error_log_window_minutes)
        end = datetime.now(UTC)
        start = end - window
        threshold = self._settings.detection_error_log_threshold
        findings: list[DetectionFinding] = []

        for service in services:
            try:
                result = self._logs.search(
                    service=service.name,
                    level="ERROR",
                    start=start,
                    end=end,
                    limit=200,
                )
            except LogServiceError:
                continue

            if result.total < threshold:
                continue

            findings.append(
                DetectionFinding(
                    rule_id=self.rule_id,
                    fingerprint=f"{self.rule_id}:{service.name}",
                    title=f"Error spike detected on {service.name}",
                    severity=IncidentSeverity.HIGH
                    if result.total >= threshold * 2
                    else IncidentSeverity.MEDIUM,
                    summary=(
                        f"{result.total} ERROR logs for {service.name} in the last "
                        f"{self._settings.detection_error_log_window_minutes} minutes "
                        f"(threshold={threshold})."
                    ),
                    service_names=[service.name],
                    evidence={
                        "error_count": result.total,
                        "threshold": threshold,
                        "window_minutes": self._settings.detection_error_log_window_minutes,
                        "sample_messages": [item.message for item in result.items[:5]],
                    },
                    started_at=start,
                )
            )
        return findings


class TraceLatencyRule:
    """Fire when recent traces for a service exceed latency threshold."""

    rule_id = "high_latency"

    def __init__(
        self,
        *,
        traces: TraceService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._traces = traces or TraceService()
        self._settings = settings or get_settings()

    def evaluate(self, services: list[Service]) -> list[DetectionFinding]:
        lookback = timedelta(minutes=self._settings.detection_lookback_minutes)
        end = datetime.now(UTC)
        start = end - lookback
        threshold_ms = self._settings.detection_trace_latency_ms
        findings: list[DetectionFinding] = []

        for service in services:
            try:
                result = self._traces.search(
                    service=service.name,
                    start=start,
                    end=end,
                    limit=20,
                )
            except (TraceServiceError, ValueError):
                continue

            slow = [
                trace
                for trace in result.items
                if trace.duration_ms is not None and trace.duration_ms >= threshold_ms
            ]
            if not slow:
                continue

            max_latency = max(trace.duration_ms or 0.0 for trace in slow)
            findings.append(
                DetectionFinding(
                    rule_id=self.rule_id,
                    fingerprint=f"{self.rule_id}:{service.name}",
                    title=f"High latency detected on {service.name}",
                    severity=IncidentSeverity.HIGH
                    if max_latency >= threshold_ms * 2
                    else IncidentSeverity.MEDIUM,
                    summary=(
                        f"{len(slow)} trace(s) for {service.name} exceeded "
                        f"{threshold_ms:.0f}ms (max={max_latency:.0f}ms) in the last "
                        f"{self._settings.detection_lookback_minutes} minutes."
                    ),
                    service_names=[service.name],
                    evidence={
                        "slow_trace_count": len(slow),
                        "threshold_ms": threshold_ms,
                        "max_latency_ms": max_latency,
                        "trace_ids": [trace.trace_id for trace in slow[:5]],
                    },
                    started_at=start,
                )
            )
        return findings


class TraceErrorRule:
    """Fire when recent traces include error spans for a service."""

    rule_id = "trace_error"

    def __init__(
        self,
        *,
        traces: TraceService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._traces = traces or TraceService()
        self._settings = settings or get_settings()

    def evaluate(self, services: list[Service]) -> list[DetectionFinding]:
        lookback = timedelta(minutes=self._settings.detection_lookback_minutes)
        end = datetime.now(UTC)
        start = end - lookback
        threshold = self._settings.detection_trace_error_threshold
        findings: list[DetectionFinding] = []

        for service in services:
            try:
                result = self._traces.search(
                    service=service.name,
                    start=start,
                    end=end,
                    limit=20,
                )
            except (TraceServiceError, ValueError):
                continue

            errored = [
                trace
                for trace in result.items
                if any(span.status == "error" and span.service == service.name for span in trace.spans)
                or (
                    # fallback when span details omitted from search payload
                    service.name in trace.services
                    and any(span.status == "error" for span in trace.spans)
                )
            ]
            # Also count traces where any span is error and service is in affected list
            if not errored:
                errored = [
                    trace
                    for trace in result.items
                    if any(span.status == "error" for span in trace.spans)
                    and service.name in trace.services
                ]

            if len(errored) < threshold:
                continue

            findings.append(
                DetectionFinding(
                    rule_id=self.rule_id,
                    fingerprint=f"{self.rule_id}:{service.name}",
                    title=f"Trace errors detected on {service.name}",
                    severity=IncidentSeverity.HIGH,
                    summary=(
                        f"{len(errored)} recent trace(s) involving {service.name} "
                        f"contain error spans (threshold={threshold})."
                    ),
                    service_names=[service.name],
                    evidence={
                        "error_trace_count": len(errored),
                        "threshold": threshold,
                        "trace_ids": [trace.trace_id for trace in errored[:5]],
                    },
                    started_at=start,
                )
            )
        return findings
