from __future__ import annotations

import json
from typing import Any

import redis
from redis.exceptions import RedisError, ResponseError

from app.clients.redis import get_redis_client
from app.core.config import get_settings


class StreamServiceError(RuntimeError):
    """Raised when Redis Streams operations fail."""


class StreamPublisher:
    """
    Thin Redis Streams publisher used to fan out telemetry events.

    Full consumer workers land in a later phase; this skeleton establishes
    stream names, consumer groups, and a stable publish API.
    """

    def __init__(self, client: redis.Redis | None = None) -> None:
        self._settings = get_settings()
        self._client = client or get_redis_client()

    @property
    def logs_stream(self) -> str:
        return self._settings.redis_logs_stream

    @property
    def incident_events_stream(self) -> str:
        return self._settings.redis_incident_events_stream

    def ensure_detection_consumer_group(self) -> None:
        """Create the detection consumer group if missing (idempotent)."""
        self._ensure_group(
            stream=self.incident_events_stream,
            group=self._settings.redis_detection_consumer_group,
        )

    def publish_log_event(self, payload: dict[str, Any]) -> str:
        return self._xadd(self.logs_stream, payload)

    def publish_incident_event(self, payload: dict[str, Any]) -> str:
        self.ensure_detection_consumer_group()
        return self._xadd(self.incident_events_stream, payload)

    def _ensure_group(self, *, stream: str, group: str) -> None:
        try:
            self._client.xgroup_create(stream, group, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise StreamServiceError(f"Failed to create consumer group: {exc}") from exc
        except RedisError as exc:
            raise StreamServiceError(f"Redis unavailable: {exc}") from exc

    def _xadd(self, stream: str, payload: dict[str, Any]) -> str:
        try:
            message_id = self._client.xadd(
                stream,
                {"payload": json.dumps(payload, default=str)},
            )
        except RedisError as exc:
            raise StreamServiceError(f"Failed to publish to {stream}: {exc}") from exc
        return str(message_id)
