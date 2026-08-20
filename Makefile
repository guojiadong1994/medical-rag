.PHONY: dev test lint api web infra-up infra-down preflight product-start

dev:
	pip install -e ".[product,dev]"

test:
	pytest -q

lint:
	ruff check src tests

api:
	python run.py

web:
	cd apps/web && npm run dev

preflight:
	python scripts/preflight_v1.py

product-start:
	@echo "请分别运行: python run.py 以及 cd apps/web && npm run dev"

infra-up:
	docker compose up -d

infra-down:
	docker compose down
