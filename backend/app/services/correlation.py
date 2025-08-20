from __future__ import annotations

from app.schemas.logs import LogDocument
from app.schemas.traces import TraceRead
from app.services.logs import LogService, LogServiceError
from app.services.traces import TraceService, TraceServiceError
from pydantic import BaseModel, Field


class TraceCorrelationResult(BaseModel):
    trace_id: str
    trace: TraceRead | None = None
    logs_by_service: dict[str, list[LogDocument]] = Field(default_factory=dict)
    affected_services: list[str] = Field(default_factory=list)
    log_count: int = 0
    span_count: int = 0


class CorrelationServiceError(RuntimeError):
    """Raised when cross-signal correlation fails."""


class CorrelationService:
    """Correlate traces and logs using shared trace IDs."""

    def __init__(
        self,
        *,
        traces: TraceService | None = None,
        logs: LogService | None = None,
    ) -> None:
        self._traces = traces or TraceService()
        self._logs = logs or LogService()

    def by_trace_id(self, trace_id: str, *, log_limit: int = 100) -> TraceCorrelationResult:
        try:
            trace = self._traces.get_trace(trace_id)
        except TraceServiceError as exc:
            raise CorrelationServiceError(str(exc)) from exc

        try:
            logs_grouped = self._logs.correlate(trace_id=trace_id, limit=log_limit)
        except (LogServiceError, ValueError) as exc:
            raise CorrelationServiceError(str(exc)) from exc

        services = set(logs_grouped.keys())
        if trace is not None:
            services.update(trace.services)

        log_count = sum(len(items) for items in logs_grouped.values())
        return TraceCorrelationResult(
            trace_id=trace.trace_id if trace is not None else trace_id,
            trace=trace,
            logs_by_service=logs_grouped,
            affected_services=sorted(services),
            log_count=log_count,
            span_count=trace.span_count if trace is not None else 0,
        )
