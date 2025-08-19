from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SpanIngest(BaseModel):
    span_id: str = Field(min_length=1, max_length=32)
    parent_span_id: str | None = Field(default=None, max_length=32)
    service: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=256)
    start_time: datetime
    duration_ms: float = Field(ge=0)
    status: str = Field(default="ok", max_length=32)
    tags: dict[str, str] = Field(default_factory=dict)


class TraceIngest(BaseModel):
    trace_id: str = Field(min_length=1, max_length=32)
    spans: list[SpanIngest] = Field(min_length=1)


class SpanRead(BaseModel):
    span_id: str
    parent_span_id: str | None = None
    service: str
    operation: str
    start_time: datetime | None = None
    duration_ms: float | None = None
    status: str | None = None
    tags: dict[str, Any] = Field(default_factory=dict)


class TraceRead(BaseModel):
    trace_id: str
    services: list[str] = Field(default_factory=list)
    span_count: int = 0
    duration_ms: float | None = None
    spans: list[SpanRead] = Field(default_factory=list)


class TraceSearchResult(BaseModel):
    total: int
    items: list[TraceRead]


class TraceIngestResult(BaseModel):
    trace_id: str
    span_count: int
    status: str = "accepted"
