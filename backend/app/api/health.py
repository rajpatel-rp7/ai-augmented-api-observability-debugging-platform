import logging

import psycopg
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


def _psycopg_dsn(database_url: str) -> str:
    """Convert a SQLAlchemy-style URL to a plain psycopg DSN if needed."""
    prefix = "postgresql+psycopg://"
    if database_url.startswith(prefix):
        return "postgresql://" + database_url.removeprefix(prefix)
    return database_url


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — process is up; does not check dependencies."""
    settings = get_settings()
    return {"status": "ok", "service": settings.app_name}


@router.get("/ready")
def ready() -> JSONResponse:
    """Readiness probe — verifies PostgreSQL connectivity."""
    settings = get_settings()
    dsn = _psycopg_dsn(settings.database_url)

    try:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except psycopg.Error as exc:
        logger.warning("Readiness check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "service": settings.app_name,
                "database": "unreachable",
                "detail": str(exc),
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "ready",
            "service": settings.app_name,
            "database": "ok",
        },
    )
