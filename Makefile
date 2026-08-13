.PHONY: dev test lint api infra-up infra-down

dev:
	pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check src tests

api:
	uvicorn medical_rag.api.app:app --reload --host 0.0.0.0 --port 8000

infra-up:
	docker compose up -d

infra-down:
	docker compose down
