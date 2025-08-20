from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.services.correlation import (
    CorrelationService,
    CorrelationServiceError,
    TraceCorrelationResult,
)

router = APIRouter(prefix="/correlate", tags=["correlation"])


def get_correlation_service() -> CorrelationService:
    return CorrelationService()


@router.get("/trace/{trace_id}", response_model=TraceCorrelationResult)
def correlate_by_trace_id(
    trace_id: str,
    log_limit: int = Query(default=100, ge=1, le=200),
    correlation: CorrelationService = Depends(get_correlation_service),
) -> TraceCorrelationResult:
    """Join Jaeger spans and Elasticsearch logs for a single trace ID."""
    try:
        result = correlation.by_trace_id(trace_id, log_limit=log_limit)
    except CorrelationServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if result.trace is None and result.log_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No trace or logs found for trace_id",
        )
    return result
