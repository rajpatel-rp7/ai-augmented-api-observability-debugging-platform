# AI-Augmented API Observability & Auto-Debugging Platform

Centralized platform for collecting and correlating application logs, metrics, and distributed traces across services. Detects anomalies, surfaces incidents, and uses an AI-assisted layer to summarize root causes and suggest next investigation steps.

> **Status:** Phases 1–8 — platform API, telemetry backends, detection, AI analysis, synthetic generator, and React dashboard MVP.

## Goals

- Correlate telemetry (logs, metrics, traces) by service, time window, and trace ID
- Detect abnormal behaviour (latency spikes, error rates, service failures)
- Provide AI-assisted incident summaries and recommended investigation steps
- Expose a unified API and React dashboard for system health

## Tech stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.12, FastAPI, SQLAlchemy, PostgreSQL |
| Observability | OpenTelemetry, Prometheus, Grafana, Jaeger |
| Logging | Elasticsearch |
| Messaging | Redis Streams |
| AI | OpenAI API (heuristic stub fallback) |
| Frontend | React + TypeScript (Vite) |
| Demo | Synthetic telemetry generator |
| Infra | Docker Compose (local); Kubernetes (later) |

## Architecture (target)

Microservices emit telemetry via OpenTelemetry → Collector → Prometheus / Elasticsearch / trace backend. This platform queries those backends, correlates signals, detects incidents, and runs AI analysis. For local demos, the synthetic generator posts the payment-timeout scenario into the platform APIs.

Current local path:

- API metrics → Prometheus → Grafana
- Structured logs → Elasticsearch
- Traces → Jaeger
- Correlate logs + spans by `trace_id`
- Rule-based detection creates incidents
- AI analysis summarizes incidents (OpenAI when configured, otherwise stub)
- Generator + React dashboard under Compose profile `demo`

## Getting started

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local runs outside Docker)
- Node.js 20+ (for local dashboard development)

### Run with Docker Compose

```bash
cp .env.example .env
# optional: set OPENAI_API_KEY in .env for live LLM analysis
docker compose up --build
```

Core stack:

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin by default) |
| Elasticsearch | http://localhost:9200 |
| Redis | localhost:6379 |
| Jaeger UI | http://localhost:16686 |

Demo profile (generator + dashboard):

```bash
docker compose --profile demo up --build
```

| Service | URL |
|---------|-----|
| React dashboard | http://localhost:5173 |
| Generator | loops against `http://api:8000` |

Useful API routes:

- Services / Incidents: `/api/v1/services`, `/api/v1/incidents`
- Analyze incident: `POST /api/v1/incidents/{id}/analyze`
- Latest analysis: `GET /api/v1/incidents/{id}/analysis`
- Detection: `GET /api/v1/detection/rules`, `POST /api/v1/detection/run`
- Logs / Traces / Correlate: `/api/v1/logs`, `/api/v1/traces`, `/api/v1/correlate/trace/{trace_id}`
- OpenAPI docs: http://localhost:8000/docs

If `OPENAI_API_KEY` is empty (default), analysis uses a deterministic heuristic stub so demos work offline.

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

### Local dashboard

```bash
cd frontend
npm install
npm run dev
```

### Synthetic generator

```bash
cd generators
pip install -e .
python generate_telemetry.py --api-url http://localhost:8000 --burst 6
```

### Tests

```bash
cd backend
pytest
```

## Project layout

```
backend/                 FastAPI application (API, models, schemas, clients, services, workers)
frontend/                React + TypeScript dashboard MVP
generators/              Synthetic payment-timeout telemetry emitter
prometheus/              Prometheus scrape config
grafana/provisioning/    Datasource + starter dashboard
docker-compose.yml
.env.example
```

## License

Proprietary — internal / portfolio project.
