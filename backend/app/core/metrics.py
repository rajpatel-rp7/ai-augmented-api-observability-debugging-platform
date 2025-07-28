"""Prometheus HTTP metrics for the FastAPI application."""

from collections.abc import Callable
from time import perf_counter

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests processed by the observability API.",
    ["method", "handler", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "handler"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

EXCLUDED_PATHS = {
    "/metrics",
    "/health",
    "/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
}


def _resolve_handler(request: Request) -> str:
    """Prefer the matched route template to avoid high-cardinality path labels."""
    route = request.scope.get("route")
    template = getattr(route, "path", None) if route is not None else None
    if not isinstance(template, str) or not template:
        return request.url.path

    raw_path = request.url.path
    if template == raw_path or template.startswith("/api/"):
        return template

    # Included routers often expose path without the app-level prefix.
    static_prefix = template.split("{", 1)[0].rstrip("/")
    if static_prefix:
        idx = raw_path.find(static_prefix)
        if idx > 0:
            return f"{raw_path[:idx]}{template}"

    return template


def setup_metrics(app: FastAPI) -> None:
    """Register request metrics middleware and the /metrics scrape endpoint."""

    @app.middleware("http")
    async def prometheus_middleware(
        request: Request,
        call_next: Callable,
    ) -> Response:
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        started = perf_counter()
        response = await call_next(request)
        elapsed = perf_counter() - started

        handler = _resolve_handler(request)
        method = request.method
        status = str(response.status_code)

        REQUEST_COUNT.labels(method=method, handler=handler, status=status).inc()
        REQUEST_LATENCY.labels(method=method, handler=handler).observe(elapsed)
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
