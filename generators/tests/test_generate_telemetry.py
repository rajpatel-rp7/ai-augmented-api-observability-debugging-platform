"""Lightweight unit checks for the synthetic generator helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generate_telemetry import (  # noqa: E402
    PlatformClient,
    SERVICES,
    _hex_id,
    emit_payment_timeout_scenario,
    run_once,
)


def test_hex_id_width() -> None:
    assert len(_hex_id(16)) == 16
    assert len(_hex_id(32)) == 32
    assert all(c in "0123456789abcdef" for c in _hex_id(32))


def test_emit_payment_timeout_posts_logs_and_trace() -> None:
    client = MagicMock(spec=PlatformClient)
    trace_id = emit_payment_timeout_scenario(client, healthy=False)

    assert len(trace_id) == 32
    assert client.ingest_log.call_count >= 4
    client.ingest_trace.assert_called_once()
    payload = client.ingest_trace.call_args.args[0]
    assert payload["trace_id"] == trace_id
    assert len(payload["spans"]) == 3
    assert any(call.args[0]["level"] == "ERROR" for call in client.ingest_log.call_args_list)


def test_run_once_ensures_services_and_detection() -> None:
    client = MagicMock(spec=PlatformClient)
    client.ensure_services.return_value = {s["name"]: "id" for s in SERVICES}
    client.run_detection.return_value = {"findings": [], "created_incidents": []}

    run_once(client, burst=2, run_detection=True)

    client.ensure_services.assert_called_once()
    assert client.ingest_trace.call_count == 2
    client.run_detection.assert_called_once()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
