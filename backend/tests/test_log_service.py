from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.schemas.logs import LogIngest
from app.services.logs import LogService, LogServiceError


@pytest.fixture()
def es_client() -> MagicMock:
    client = MagicMock()
    client.indices.exists.return_value = True
    return client


def test_ingest_indexes_document(es_client: MagicMock) -> None:
    es_client.index.return_value = {"_id": "log-1"}
    service = LogService(client=es_client)

    doc = service.ingest(
        LogIngest(
            service="payment-service",
            level="error",
            message="database timeout",
            trace_id="trace-123",
        )
    )

    assert doc.id == "log-1"
    assert doc.level == "ERROR"
    assert doc.service == "payment-service"
    es_client.index.assert_called_once()
    kwargs = es_client.index.call_args.kwargs
    assert kwargs["document"]["service"] == "payment-service"
    assert kwargs["document"]["level"] == "ERROR"
    assert "@timestamp" in kwargs["document"]


def test_search_builds_filters_and_maps_hits(es_client: MagicMock) -> None:
    es_client.search.return_value = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_id": "abc",
                    "_source": {
                        "@timestamp": "2025-08-10T12:00:00+00:00",
                        "service": "payment-service",
                        "level": "ERROR",
                        "message": "database timeout",
                        "trace_id": "trace-123",
                        "attributes": {"db": "payments"},
                    },
                }
            ],
        }
    }
    service = LogService(client=es_client)
    result = service.search(service="payment-service", trace_id="trace-123", level="error")

    assert result.total == 1
    assert result.items[0].id == "abc"
    assert result.items[0].trace_id == "trace-123"

    query = es_client.search.call_args.kwargs["query"]["bool"]["filter"]
    assert {"term": {"service": "payment-service"}} in query
    assert {"term": {"trace_id": "trace-123"}} in query
    assert {"term": {"level": "ERROR"}} in query


def test_correlate_groups_by_service(es_client: MagicMock) -> None:
    es_client.search.return_value = {
        "hits": {
            "total": {"value": 2},
            "hits": [
                {
                    "_id": "1",
                    "_source": {
                        "@timestamp": datetime.now(UTC).isoformat(),
                        "service": "payment-service",
                        "level": "ERROR",
                        "message": "timeout",
                        "trace_id": "t1",
                    },
                },
                {
                    "_id": "2",
                    "_source": {
                        "@timestamp": datetime.now(UTC).isoformat(),
                        "service": "order-service",
                        "level": "WARN",
                        "message": "downstream failure",
                        "trace_id": "t1",
                    },
                },
            ],
        }
    }
    service = LogService(client=es_client)
    grouped = service.correlate(trace_id="t1")
    assert set(grouped.keys()) == {"payment-service", "order-service"}
    assert len(grouped["payment-service"]) == 1


def test_correlate_requires_trace_or_service(es_client: MagicMock) -> None:
    service = LogService(client=es_client)
    with pytest.raises(ValueError):
        service.correlate()


def test_search_wraps_connection_errors(es_client: MagicMock) -> None:
    from elasticsearch.exceptions import ConnectionError as ESConnectionError

    es_client.search.side_effect = ESConnectionError("down")
    service = LogService(client=es_client)
    with pytest.raises(LogServiceError):
        service.search(service="payment-service")
