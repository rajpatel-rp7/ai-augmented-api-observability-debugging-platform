from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.traces import (
    TraceIngest,
    TraceIngestResult,
    TraceRead,
    TraceSearchResult,
)
from app.services.traces import TraceService, TraceServiceError

router = APIRouter(prefix="/traces", tags=["traces"])


def get_trace_service() -> TraceService:
    return TraceService()


@router.post("", response_model=TraceIngestResult, status_code=status.HTTP_202_ACCEPTED)
def ingest_trace(
    payload: TraceIngest,
    traces: TraceService = Depends(get_trace_service),
) -> TraceIngestResult:
    """
    Ingest a simplified trace via Jaeger's Zipkin endpoint.

    Useful for local demos and the future synthetic generator until services
    emit OTLP directly.
    """
    try:
        return traces.ingest(payload)
    except TraceServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/services", response_model=list[str])
def list_trace_services(traces: TraceService = Depends(get_trace_service)) -> list[str]:
    try:
        return traces.list_services()
    except TraceServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/search", response_model=TraceSearchResult)
def search_traces(
    service: str = Query(..., description="Service name required by Jaeger search"),
    operation: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    traces: TraceService = Depends(get_trace_service),
) -> TraceSearchResult:
    try:
        return traces.search(
            service=service,
            operation=operation,
            start=start,
            end=end,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TraceServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/{trace_id}", response_model=TraceRead)
def get_trace(trace_id: str, traces: TraceService = Depends(get_trace_service)) -> TraceRead:
    try:
        trace = traces.get_trace(trace_id)
    except TraceServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
    return trace
