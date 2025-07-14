# AI-Augmented API Observability & Auto-Debugging Platform

Centralized platform for collecting and correlating application logs, metrics, and distributed traces across services. Detects anomalies, surfaces incidents, and uses an AI-assisted layer to summarize root causes and suggest next investigation steps.

> **Status:** Early scaffolding. The API and Postgres stack are bootable; ingestion, detection, and AI analysis land in later iterations.

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

## Getting started (Phase 1)

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local runs outside Docker)

### Run with Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

API: `http://localhost:8000`

- Health: `GET /health`
- Readiness: `GET /ready`
- OpenAPI docs: `http://localhost:8000/docs`

### Local development (API only)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Tests

```bash
cd backend
pytest
```

## Project layout

```
backend/          FastAPI application
docker-compose.yml
.env.example
```

Additional packages (generators, frontend, OTel collector config, k8s) will be added as features land.

## License

Proprietary — internal / portfolio project.
