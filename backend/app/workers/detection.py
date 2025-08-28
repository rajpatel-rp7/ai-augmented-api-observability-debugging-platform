from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.detection import DetectionService

logger = logging.getLogger(__name__)


def run_detection_once() -> dict[str, object]:
    """Synchronous single detection pass used by API and background loop."""
    with SessionLocal() as db:
        result = DetectionService().run(db)
        return {
            "evaluated_at": result.evaluated_at.isoformat(),
            "findings": len(result.findings),
            "created_incident_ids": [str(item) for item in result.created_incident_ids],
            "skipped_fingerprints": result.skipped_fingerprints,
        }


async def detection_loop(stop_event: asyncio.Event) -> None:
    """Periodically evaluate detection rules until stop_event is set."""
    settings = get_settings()
    interval = max(settings.detection_interval_seconds, 15)
    logger.info("Detection loop started (interval=%ss)", interval)

    while not stop_event.is_set():
        if settings.detection_enabled:
            try:
                summary = await asyncio.to_thread(run_detection_once)
                if summary["created_incident_ids"]:
                    logger.info(
                        "Detection created %s incident(s)",
                        len(summary["created_incident_ids"]),
                    )
            except Exception:  # noqa: BLE001
                logger.exception("Detection loop iteration failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            continue

    logger.info("Detection loop stopped")
