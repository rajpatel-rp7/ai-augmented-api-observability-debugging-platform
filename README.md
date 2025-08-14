# AI-Augmented API Observability & Auto-Debugging Platform

Centralized platform for collecting and correlating application logs, metrics, and distributed traces across services. Detects anomalies, surfaces incidents, and uses an AI-assisted layer to summarize root causes and suggest next investigation steps.

> **Status:** Core API, Postgres models, Prometheus/Grafana metrics, Elasticsearch log search/correlation, and a Redis Streams publisher skeleton. Trace backend and automated detection come next.

## Goals

- Correlate telemetry (logs, metrics, traces) by service, time window, and trace ID
- Detect abnormal behaviour (latency spikes, error rates, service failures)
- Provide AI-assisted incident summaries and recommended investigation steps
- Expose a unified API and (later) a React dashboard for system health

## Tech stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.12, FastAPI, SQLAlchemy, PostgreSQL |
| Observability | OpenTelemetry, Prometheus, Grafana |
| Logging | Elasticsearch |
| Messaging | Redis Streams |
| AI | OpenAI API |
| Frontend | React + TypeScript (planned) |
| Infra | Docker Compose (local); Kubernetes (later) |

## Architecture (target)

Microservices emit telemetry via OpenTelemetry → Collector → Prometheus / Elasticsearch / trace backend. This platform queries those backends, correlates signals, detects incidents, and runs AI analysis. For local demos, a synthetic telemetry generator will stand in for real services.

Current local path:

- API metrics → Prometheus → Grafana
- Structured logs → Elasticsearch (search/correlate APIs)
- Log/incident events → Redis Streams (publisher + consumer group skeleton)

## Getting started

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local runs outside Docker)

### Run with Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin by default) |
| Elasticsearch | http://localhost:9200 |
| Redis | localhost:6379 |

Useful API routes:

- Health: `GET /health`
- Readiness: `GET /ready`
- Metrics: `GET /metrics`
- Services: `GET/POST /api/v1/services`
- Incidents: `GET/POST /api/v1/incidents`
- Logs ingest: `POST /api/v1/logs`
- Logs search: `GET /api/v1/logs/search`
- Logs correlate: `GET /api/v1/logs/correlate?trace_id=...`
- OpenAPI docs: http://localhost:8000/docs

Migrations run automatically on API container start (`alembic upgrade head`).

### Local development (API only)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Point `ELASTICSEARCH_URL` and `REDIS_URL` at local containers when running the API outside Compose.

### Tests

```bash
cd backend
pytest
```

## Project layout

```
backend/                 FastAPI application (API, models, schemas, clients, services)
prometheus/              Prometheus scrape config
grafana/provisioning/    Datasource + starter dashboard
docker-compose.yml
.env.example
```

Additional packages (generators, frontend, OTel collector config, k8s) will be added as features land.

## License

Proprietary — internal / portfolio project.
