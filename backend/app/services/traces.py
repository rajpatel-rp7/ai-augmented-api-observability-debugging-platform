from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.clients.jaeger import JaegerClient, JaegerClientError
from app.schemas.traces import (
    SpanRead,
    TraceIngest,
    TraceIngestResult,
    TraceRead,
    TraceSearchResult,
)


class TraceServiceError(RuntimeError):
    """Raised when trace backend operations fail."""


def _normalize_hex_id(value: str, width: int) -> str:
    cleaned = value.lower().removeprefix("0x")
    if not all(ch in "0123456789abcdef" for ch in cleaned):
        raise ValueError(f"Invalid hex id: {value}")
    return cleaned.zfill(width)[-width:]


def _datetime_to_micros(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp() * 1_000_000)


def _micros_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1_000_000, tz=UTC)


class TraceService:
    """Query and ingest distributed traces via Jaeger."""

    def __init__(self, client: JaegerClient | None = None) -> None:
        self._client = client or JaegerClient()

    def ingest(self, payload: TraceIngest) -> TraceIngestResult:
        try:
            trace_id = _normalize_hex_id(payload.trace_id, 32)
            zipkin_spans: list[dict[str, Any]] = []
            for span in payload.spans:
                span_id = _normalize_hex_id(span.span_id, 16)
                parent_id = (
                    _normalize_hex_id(span.parent_span_id, 16) if span.parent_span_id else None
                )
                tags = {key: str(value) for key, value in span.tags.items()}
                if span.status.lower() in {"error", "failed", "fault"}:
                    tags["error"] = "true"
                tags["otel.status_code"] = span.status.upper()

                zipkin_span: dict[str, Any] = {
                    "traceId": trace_id,
                    "id": span_id,
                    "name": span.operation,
                    "timestamp": _datetime_to_micros(span.start_time),
                    "duration": int(span.duration_ms * 1000),
                    "localEndpoint": {"serviceName": span.service},
                    "tags": tags,
                }
                if parent_id:
                    zipkin_span["parentId"] = parent_id
                zipkin_spans.append(zipkin_span)

            self._client.ingest_zipkin_spans(zipkin_spans)
        except (JaegerClientError, ValueError) as exc:
            raise TraceServiceError(f"Failed to ingest trace: {exc}") from exc

        return TraceIngestResult(trace_id=trace_id, span_count=len(payload.spans))

    def get_trace(self, trace_id: str) -> TraceRead | None:
        try:
            normalized = _normalize_hex_id(trace_id, 32)
            raw = self._client.get_trace(normalized)
        except (JaegerClientError, ValueError) as exc:
            raise TraceServiceError(f"Failed to fetch trace: {exc}") from exc
        if raw is None:
            return None
        return self._parse_jaeger_trace(raw)

    def search(
        self,
        *,
        service: str | None = None,
        operation: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 20,
    ) -> TraceSearchResult:
        if not service:
            # Jaeger search requires a service name.
            raise ValueError("service is required for trace search")

        try:
            raw_traces = self._client.search_traces(
                service=service,
                operation=operation,
                start_us=_datetime_to_micros(start) if start else None,
                end_us=_datetime_to_micros(end) if end else None,
                limit=limit,
            )
        except JaegerClientError as exc:
            raise TraceServiceError(f"Failed to search traces: {exc}") from exc

        items = [self._parse_jaeger_trace(item) for item in raw_traces]
        return TraceSearchResult(total=len(items), items=items)

    def list_services(self) -> list[str]:
        try:
            return self._client.list_services()
        except JaegerClientError as exc:
            raise TraceServiceError(f"Failed to list trace services: {exc}") from exc

    def _parse_jaeger_trace(self, raw: dict[str, Any]) -> TraceRead:
        processes = raw.get("processes") or {}
        spans_raw = raw.get("spans") or []
        trace_id = ""
        spans: list[SpanRead] = []
        services: set[str] = set()
        min_start: int | None = None
        max_end: int | None = None

        for span in spans_raw:
            trace_id = span.get("traceID") or trace_id
            process_key = span.get("processID")
            process = processes.get(process_key) or {}
            service = process.get("serviceName") or "unknown"
            services.add(service)

            start = span.get("startTime")
            duration = span.get("duration")
            if isinstance(start, int):
                min_start = start if min_start is None else min(min_start, start)
                if isinstance(duration, int):
                    end = start + duration
                    max_end = end if max_end is None else max(max_end, end)

            tags = {
                tag.get("key"): tag.get("value")
                for tag in (span.get("tags") or [])
                if tag.get("key")
            }
            status = "error" if tags.get("error") in {True, "true", "1"} else "ok"
            parent_span_id = None
            for ref in span.get("references") or []:
                if ref.get("refType") == "CHILD_OF":
                    parent_span_id = ref.get("spanID")
                    break

            spans.append(
                SpanRead(
                    span_id=span.get("spanID") or "",
                    parent_span_id=parent_span_id,
                    service=service,
                    operation=span.get("operationName") or "unknown",
                    start_time=_micros_to_datetime(start if isinstance(start, int) else None),
                    duration_ms=(duration / 1000.0) if isinstance(duration, int) else None,
                    status=status,
                    tags=tags,
                )
            )

        duration_ms = None
        if min_start is not None and max_end is not None:
            duration_ms = (max_end - min_start) / 1000.0

        return TraceRead(
            trace_id=trace_id or raw.get("traceID") or "",
            services=sorted(services),
            span_count=len(spans),
            duration_ms=duration_ms,
            spans=spans,
        )
