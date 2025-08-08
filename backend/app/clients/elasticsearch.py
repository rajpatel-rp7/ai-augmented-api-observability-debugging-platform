from functools import lru_cache

from elasticsearch import Elasticsearch

from app.core.config import get_settings

LOGS_INDEX_MAPPINGS = {
    "properties": {
        "@timestamp": {"type": "date"},
        "service": {"type": "keyword"},
        "level": {"type": "keyword"},
        "message": {"type": "text"},
        "trace_id": {"type": "keyword"},
        "span_id": {"type": "keyword"},
        "attributes": {"type": "object", "enabled": True},
    }
}


@lru_cache
def get_elasticsearch_client() -> Elasticsearch:
    settings = get_settings()
    return Elasticsearch(
        settings.elasticsearch_url,
        request_timeout=10,
        retry_on_timeout=True,
        max_retries=2,
    )


def ensure_logs_index(client: Elasticsearch | None = None) -> None:
    """Create the application logs index if it does not already exist."""
    settings = get_settings()
    es = client or get_elasticsearch_client()
    index = settings.elasticsearch_logs_index
    if not es.indices.exists(index=index):
        es.indices.create(index=index, mappings=LOGS_INDEX_MAPPINGS)
