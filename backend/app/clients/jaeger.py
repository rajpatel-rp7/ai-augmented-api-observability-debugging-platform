from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings


class JaegerClientError(RuntimeError):
    """Raised when Jaeger HTTP calls fail."""


class JaegerClient:
    """Thin HTTP client for Jaeger Query + Zipkin ingest endpoints."""

    def __init__(
        self,
        *,
        query_url: str | None = None,
        zipkin_url: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self._query_url = (query_url or settings.jaeger_query_url).rstrip("/")
        self._zipkin_url = (zipkin_url or settings.jaeger_zipkin_url).rstrip("/")
        self._timeout = timeout if timeout is not None else settings.jaeger_timeout_seconds
        self._client = client or httpx.Client(timeout=self._timeout)

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        response = self._request("GET", f"{self._query_url}/api/traces/{trace_id}")
        if response.status_code == 404:
            return None
        self._raise_for_status(response, "fetch trace")
        payload = response.json()
        data = payload.get("data") or []
        return data[0] if data else None

    def search_traces(
        self,
        *,
        service: str | None = None,
        operation: str | None = None,
        start_us: int | None = None,
        end_us: int | None = None,
        limit: int = 20,
        tags: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if service:
            params["service"] = service
        if operation:
            params["operation"] = operation
        if start_us is not None:
            params["start"] = start_us
        if end_us is not None:
            params["end"] = end_us
        if tags:
            # Jaeger expects a JSON object string for tags.
            import json

            params["tags"] = json.dumps(tags)

        response = self._request("GET", f"{self._query_url}/api/traces", params=params)
        self._raise_for_status(response, "search traces")
        payload = response.json()
        return list(payload.get("data") or [])

    def list_services(self) -> list[str]:
        response = self._request("GET", f"{self._query_url}/api/services")
        self._raise_for_status(response, "list services")
        payload = response.json()
        return list(payload.get("data") or [])

    def ingest_zipkin_spans(self, spans: list[dict[str, Any]]) -> None:
        response = self._request(
            "POST",
            f"{self._zipkin_url}/api/v2/spans",
            json=spans,
        )
        # Zipkin ingest commonly returns 202 Accepted.
        if response.status_code not in (200, 202, 204):
            raise JaegerClientError(
                f"Failed to ingest spans: HTTP {response.status_code} {response.text}"
            )

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise JaegerClientError(f"Jaeger request failed: {exc}") from exc

    @staticmethod
    def _raise_for_status(response: httpx.Response, action: str) -> None:
        if response.is_error:
            raise JaegerClientError(
                f"Failed to {action}: HTTP {response.status_code} {response.text}"
            )
