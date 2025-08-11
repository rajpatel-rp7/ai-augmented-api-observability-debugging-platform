from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.logs import LogCorrelateResult, LogDocument, LogIngest, LogSearchResult
from app.services.logs import LogService, LogServiceError
from app.services.streams import StreamPublisher, StreamServiceError

router = APIRouter(prefix="/logs", tags=["logs"])


def get_log_service() -> LogService:
    return LogService()


def get_stream_publisher() -> StreamPublisher:
    return StreamPublisher()


@router.post("", response_model=LogDocument, status_code=status.HTTP_201_CREATED)
def ingest_log(
    payload: LogIngest,
    logs: LogService = Depends(get_log_service),
    streams: StreamPublisher = Depends(get_stream_publisher),
) -> LogDocument:
    """
    Ingest a structured log document.

    Intended for local/dev and synthetic generators until OTel pipelines feed ES directly.
    """
    try:
        document = logs.ingest(payload)
    except LogServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    try:
        streams.publish_log_event(document.model_dump(by_alias=True, mode="json"))
    except StreamServiceError:
        # Indexing succeeded; stream fan-out is best-effort in this phase.
        pass

    return document


@router.get("/search", response_model=LogSearchResult)
def search_logs(
    service: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    level: str | None = Query(default=None),
    query: str | None = Query(default=None, description="Simple query string over message/service"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    logs: LogService = Depends(get_log_service),
) -> LogSearchResult:
    try:
        return logs.search(
            service=service,
            trace_id=trace_id,
            level=level,
            query=query,
            start=start,
            end=end,
            limit=limit,
        )
    except LogServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/correlate", response_model=LogCorrelateResult)
def correlate_logs(
    trace_id: str | None = Query(default=None),
    service: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    logs: LogService = Depends(get_log_service),
) -> LogCorrelateResult:
    try:
        grouped = logs.correlate(
            trace_id=trace_id,
            service=service,
            start=start,
            end=end,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LogServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    total = sum(len(items) for items in grouped.values())
    return LogCorrelateResult(
        trace_id=trace_id,
        service=service,
        services=grouped,
        total=total,
    )
