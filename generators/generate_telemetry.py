from __future__ import annotations

import argparse
import logging
import random
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx

logger = logging.getLogger("generator")

SERVICES = [
    {
        "name": "order-service",
        "display_name": "Order Service",
        "owner_team": "commerce",
    },
    {
        "name": "payment-service",
        "display_name": "Payment Service",
        "owner_team": "payments",
    },
    {
        "name": "notification-service",
        "display_name": "Notification Service",
        "owner_team": "comms",
    },
]


class PlatformClient:
    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base, timeout=timeout)

    def ensure_services(self) -> dict[str, str]:
        existing = {
            item["name"]: item["id"]
            for item in self._client.get("/api/v1/services").json()
        }
        ids: dict[str, str] = {}
        for service in SERVICES:
            if service["name"] in existing:
                ids[service["name"]] = existing[service["name"]]
                continue
            created = self._client.post("/api/v1/services", json=service)
            if created.status_code == 409:
                # Race with another generator; refresh list.
                refreshed = {
                    item["name"]: item["id"]
                    for item in self._client.get("/api/v1/services").json()
                }
                ids[service["name"]] = refreshed[service["name"]]
                continue
            created.raise_for_status()
            ids[service["name"]] = created.json()["id"]
        return ids

    def ingest_log(self, payload: dict) -> None:
        response = self._client.post("/api/v1/logs", json=payload)
        response.raise_for_status()

    def ingest_trace(self, payload: dict) -> None:
        response = self._client.post("/api/v1/traces", json=payload)
        response.raise_for_status()

    def run_detection(self) -> dict:
        response = self._client.post("/api/v1/detection/run")
        response.raise_for_status()
        return response.json()


def _hex_id(width: int) -> str:
    return uuid.uuid4().hex[:width].ljust(width, "0")


def emit_payment_timeout_scenario(client: PlatformClient, *, healthy: bool = False) -> str:
    """
    Simulate order -> payment -> notification.

    When healthy=False, payment-service emits DB timeout errors and a slow/error span.
    """
    trace_id = _hex_id(32)
    order_span = _hex_id(16)
    payment_span = _hex_id(16)
    notify_span = _hex_id(16)
    now = datetime.now(UTC)

    client.ingest_log(
        {
            "service": "order-service",
            "level": "INFO",
            "message": "Received create-order request",
            "trace_id": trace_id,
            "span_id": order_span,
            "timestamp": now.isoformat(),
        }
    )

    if healthy:
        payment_duration_ms = random.uniform(80, 220)
        payment_status = "ok"
        client.ingest_log(
            {
                "service": "payment-service",
                "level": "INFO",
                "message": "Payment authorized",
                "trace_id": trace_id,
                "span_id": payment_span,
                "timestamp": (now + timedelta(milliseconds=40)).isoformat(),
            }
        )
    else:
        payment_duration_ms = random.uniform(3500, 5200)
        payment_status = "error"
        for idx in range(3):
            client.ingest_log(
                {
                    "service": "payment-service",
                    "level": "ERROR",
                    "message": f"database timeout while charging card (attempt={idx + 1})",
                    "trace_id": trace_id,
                    "span_id": payment_span,
                    "timestamp": (now + timedelta(milliseconds=50 + idx * 20)).isoformat(),
                    "attributes": {"error": "timeout", "db.system": "postgres"},
                }
            )
        client.ingest_log(
            {
                "service": "order-service",
                "level": "WARN",
                "message": "Payment downstream failed; order left pending",
                "trace_id": trace_id,
                "span_id": order_span,
                "timestamp": (now + timedelta(milliseconds=120)).isoformat(),
            }
        )

    client.ingest_log(
        {
            "service": "notification-service",
            "level": "INFO",
            "message": "Skipped notification because payment was not completed"
            if not healthy
            else "Sent order confirmation",
            "trace_id": trace_id,
            "span_id": notify_span,
            "timestamp": (now + timedelta(milliseconds=150)).isoformat(),
        }
    )

    client.ingest_trace(
        {
            "trace_id": trace_id,
            "spans": [
                {
                    "span_id": order_span,
                    "service": "order-service",
                    "operation": "POST /orders",
                    "start_time": now.isoformat(),
                    "duration_ms": payment_duration_ms + 40,
                    "status": "error" if not healthy else "ok",
                },
                {
                    "span_id": payment_span,
                    "parent_span_id": order_span,
                    "service": "payment-service",
                    "operation": "charge",
                    "start_time": (now + timedelta(milliseconds=20)).isoformat(),
                    "duration_ms": payment_duration_ms,
                    "status": payment_status,
                    "tags": {"db.system": "postgres"},
                },
                {
                    "span_id": notify_span,
                    "parent_span_id": order_span,
                    "service": "notification-service",
                    "operation": "send_confirmation",
                    "start_time": (now + timedelta(milliseconds=140)).isoformat(),
                    "duration_ms": random.uniform(20, 60),
                    "status": "ok",
                },
            ],
        }
    )
    return trace_id


def run_once(client: PlatformClient, *, burst: int, run_detection: bool) -> None:
    client.ensure_services()
    # Mix mostly failing payment traffic with a couple healthy requests.
    for i in range(burst):
        healthy = i % 5 == 0
        trace_id = emit_payment_timeout_scenario(client, healthy=healthy)
        logger.info("emitted scenario trace_id=%s healthy=%s", trace_id, healthy)

    if run_detection:
        result = client.run_detection()
        logger.info(
            "detection findings=%s created=%s",
            len(result.get("findings", [])),
            len(result.get("created_incidents", [])),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic observability telemetry generator")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--burst", type=int, default=6, help="Scenarios per cycle")
    parser.add_argument("--loop", action="store_true", help="Emit continuously")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between loops")
    parser.add_argument("--no-detect", action="store_true", help="Skip detection trigger")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    client = PlatformClient(args.api_url)
    try:
        while True:
            run_once(client, burst=args.burst, run_detection=not args.no_detect)
            if not args.loop:
                break
            time.sleep(args.interval)
    except httpx.HTTPError as exc:
        logger.error("generator failed talking to API: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
