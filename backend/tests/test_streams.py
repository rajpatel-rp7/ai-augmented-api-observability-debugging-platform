import json
from unittest.mock import MagicMock

import pytest
from redis.exceptions import ResponseError

from app.services.streams import StreamPublisher, StreamServiceError


@pytest.fixture()
def redis_client() -> MagicMock:
    return MagicMock()


def test_publish_log_event_serializes_payload(redis_client: MagicMock) -> None:
    redis_client.xadd.return_value = "1710000000000-0"
    publisher = StreamPublisher(client=redis_client)

    message_id = publisher.publish_log_event({"service": "payment-service", "level": "ERROR"})

    assert message_id == "1710000000000-0"
    stream, fields = redis_client.xadd.call_args.args
    assert stream == "telemetry.logs"
    assert json.loads(fields["payload"])["service"] == "payment-service"


def test_ensure_consumer_group_ignores_busygroup(redis_client: MagicMock) -> None:
    redis_client.xgroup_create.side_effect = ResponseError("BUSYGROUP Consumer Group name already exists")
    publisher = StreamPublisher(client=redis_client)
    publisher.ensure_detection_consumer_group()
    redis_client.xgroup_create.assert_called_once()


def test_publish_raises_stream_service_error(redis_client: MagicMock) -> None:
    from redis.exceptions import RedisError

    redis_client.xadd.side_effect = RedisError("boom")
    publisher = StreamPublisher(client=redis_client)
    with pytest.raises(StreamServiceError):
        publisher.publish_log_event({"service": "x"})
