from __future__ import annotations

from datetime import datetime
from typing import Any

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.exceptions import ApiError, ConnectionError as ESConnectionError

from app.clients.elasticsearch import ensure_logs_index, get_elasticsearch_client
from app.core.config import get_settings
from app.schemas.logs import LogDocument, LogIngest, LogSearchResult


class LogServiceError(RuntimeError):
    """Raised when Elasticsearch log operations fail."""


class LogService:
    """Search and correlate structured application logs stored in Elasticsearch."""

    def __init__(self, client: Elasticsearch | None = None) -> None:
        self._settings = get_settings()
        self._client = client or get_elasticsearch_client()
        self._index = self._settings.elasticsearch_logs_index

    def ingest(self, payload: LogIngest) -> LogDocument:
        ensure_logs_index(self._client)
        document = payload.to_document()
        body = document.model_dump(by_alias=True, mode="json")
        try:
            result = self._client.index(index=self._index, document=body, refresh="wait_for")
        except (ESConnectionError, ApiError) as exc:
            raise LogServiceError(f"Failed to ingest log: {exc}") from exc

        return document.model_copy(update={"id": result.get("_id")})

    def search(
        self,
        *,
        service: str | None = None,
        trace_id: str | None = None,
        level: str | None = None,
        query: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 50,
    ) -> LogSearchResult:
        filters: list[dict[str, Any]] = []
        must: list[dict[str, Any]] = []

        if service:
            filters.append({"term": {"service": service}})
        if trace_id:
            filters.append({"term": {"trace_id": trace_id}})
        if level:
            filters.append({"term": {"level": level.upper()}})
        if start or end:
            range_body: dict[str, Any] = {}
            if start:
                range_body["gte"] = start.isoformat()
            if end:
                range_body["lte"] = end.isoformat()
            filters.append({"range": {"@timestamp": range_body}})
        if query:
            must.append(
                {
                    "simple_query_string": {
                        "query": query,
                        "fields": ["message", "service", "trace_id"],
                    }
                }
            )

        bool_query: dict[str, Any] = {}
        if filters:
            bool_query["filter"] = filters
        if must:
            bool_query["must"] = must
        if not bool_query:
            bool_query["must"] = [{"match_all": {}}]

        try:
            response = self._client.search(
                index=self._index,
                query={"bool": bool_query},
                sort=[{"@timestamp": {"order": "desc"}}],
                size=min(limit, 200),
            )
        except NotFoundError:
            return LogSearchResult(total=0, items=[])
        except (ESConnectionError, ApiError) as exc:
            raise LogServiceError(f"Failed to search logs: {exc}") from exc

        hits = response.get("hits", {})
        total = hits.get("total", {})
        total_value = total.get("value", 0) if isinstance(total, dict) else int(total or 0)

        items: list[LogDocument] = []
        for hit in hits.get("hits", []):
            source = hit.get("_source", {})
            items.append(
                LogDocument(
                    id=hit.get("_id"),
                    timestamp=source.get("@timestamp"),
                    service=source.get("service"),
                    level=source.get("level"),
                    message=source.get("message"),
                    trace_id=source.get("trace_id"),
                    span_id=source.get("span_id"),
                    attributes=source.get("attributes") or {},
                )
            )

        return LogSearchResult(total=total_value, items=items)

    def correlate(
        self,
        *,
        trace_id: str | None = None,
        service: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
    ) -> dict[str, list[LogDocument]]:
        """Group matching logs by service for incident investigation."""
        if not trace_id and not service:
            raise ValueError("Provide trace_id and/or service for correlation")

        result = self.search(
            service=service,
            trace_id=trace_id,
            start=start,
            end=end,
            limit=limit,
        )
        grouped: dict[str, list[LogDocument]] = {}
        for item in result.items:
            grouped.setdefault(item.service, []).append(item)
        return grouped
