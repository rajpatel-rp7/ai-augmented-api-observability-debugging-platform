import logging

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.incidents import router as incidents_router
from app.api.services import router as services_router
from app.core.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="AI-augmented API observability and auto-debugging platform",
)

app.include_router(health_router)
app.include_router(services_router, prefix="/api/v1")
app.include_router(incidents_router, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": "0.2.0",
        "docs": "/docs",
    }
