.PHONY: help up up-demo down logs test test-generator build-frontend migrate lint-compose

help:
	@echo "Targets:"
	@echo "  up              Start core Compose stack"
	@echo "  up-demo         Start core + generator + dashboard"
	@echo "  down            Stop Compose stack"
	@echo "  logs            Tail API logs"
	@echo "  test            Run backend pytest"
	@echo "  test-generator  Run generator unit tests"
	@echo "  build-frontend  Production build of the React dashboard"
	@echo "  migrate         Run Alembic migrations locally"
	@echo "  lint-compose    Validate docker compose config"

up:
	docker compose up --build -d

up-demo:
	docker compose --profile demo up --build -d

down:
	docker compose --profile demo down

logs:
	docker compose logs -f api

test:
	cd backend && DETECTION_ENABLED=false pytest -q

test-generator:
	cd generators && pytest -q

build-frontend:
	cd frontend && npm ci && npm run build

migrate:
	cd backend && alembic upgrade head

lint-compose:
	docker compose --profile demo config --quiet
