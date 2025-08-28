import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.correlation import router as correlation_router
from app.api.detection import router as detection_router
from app.api.health import router as health_router
from app.api.incidents import router as incidents_router
from app.api.logs import router as logs_router
from app.api.services import router as services_router
from app.api.traces import router as traces_router
from app.clients.elasticsearch import ensure_logs_index
from app.core.config import get_settings
from app.core.metrics import setup_metrics
from app.services.streams import StreamPublisher, StreamServiceError
from app.workers.detection import detection_loop

settings = get_settings()
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        ensure_logs_index()
        logger.info("Elasticsearch logs index ready")
    except Exception as exc:  # noqa: BLE001 - startup should not crash if ES is still booting
        logger.warning("Elasticsearch index bootstrap skipped: %s", exc)

    try:
        StreamPublisher().ensure_detection_consumer_group()
        logger.info("Redis Streams consumer group ready")
    except StreamServiceError as exc:
        logger.warning("Redis Streams bootstrap skipped: %s", exc)

    stop_event = asyncio.Event()
    detection_task: asyncio.Task | None = None
    if settings.detection_enabled:
        detection_task = asyncio.create_task(detection_loop(stop_event))

    yield

    stop_event.set()
    if detection_task is not None:
        await detection_task


app = FastAPI(
    title=settings.app_name,
    version="0.6.0",
    description="AI-augmented API observability and auto-debugging platform",
    lifespan=lifespan,
)

setup_metrics(app)

app.include_router(health_router)
app.include_router(services_router, prefix="/api/v1")
app.include_router(incidents_router, prefix="/api/v1")
app.include_router(logs_router, prefix="/api/v1")
app.include_router(traces_router, prefix="/api/v1")
app.include_router(correlation_router, prefix="/api/v1")
app.include_router(detection_router, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": "0.6.0",
        "docs": "/docs",
        "metrics": "/metrics",
    }
