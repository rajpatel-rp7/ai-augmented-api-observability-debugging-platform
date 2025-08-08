from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LogIngest(BaseModel):
    service: str = Field(min_length=1, max_length=128)
    level: str = Field(default="INFO", max_length=16)
    message: str = Field(min_length=1)
    trace_id: str | None = Field(default=None, max_length=64)
    span_id: str | None = Field(default=None, max_length=64)
    timestamp: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    def to_document(self) -> "LogDocument":
        return LogDocument(
            timestamp=self.timestamp or datetime.now(UTC),
            service=self.service,
            level=self.level.upper(),
            message=self.message,
            trace_id=self.trace_id,
            span_id=self.span_id,
            attributes=self.attributes,
        )


class LogDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    timestamp: datetime = Field(alias="@timestamp")
    service: str
    level: str
    message: str
    trace_id: str | None = None
    span_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class LogSearchResult(BaseModel):
    total: int
    items: list[LogDocument]


class LogCorrelateResult(BaseModel):
    trace_id: str | None = None
    service: str | None = None
    services: dict[str, list[LogDocument]]
    total: int
