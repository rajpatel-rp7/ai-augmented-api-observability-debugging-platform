# Synthetic telemetry generator

Emits the demo `order-service` → `payment-service` (DB timeout) → `notification-service`
scenario into the platform APIs (logs + traces), then optionally triggers detection.

## Run locally

```bash
cd generators
python -m venv .venv
source .venv/bin/activate
pip install -e .
python generate_telemetry.py --api-url http://localhost:8000 --burst 6
```

Loop mode:

```bash
python generate_telemetry.py --loop --interval 45 --burst 6
```

## Docker Compose

```bash
docker compose --profile demo up -d generator
```
