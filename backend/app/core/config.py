from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "observability-platform"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+psycopg://observability:observability@localhost:5432/observability"
    )

    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_logs_index: str = "observability-logs"

    redis_url: str = "redis://localhost:6379/0"
    redis_logs_stream: str = "telemetry.logs"
    redis_incident_events_stream: str = "telemetry.incident-events"
    redis_detection_consumer_group: str = "detection-workers"


@lru_cache
def get_settings() -> Settings:
    return Settings()
