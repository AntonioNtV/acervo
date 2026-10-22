.PHONY: up down migrate revision test lint openapi web-check

up:
	docker compose up -d --build --wait

down:
	docker compose down

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate -m "$(m)"

test:
	uv run pytest --cov=acervo

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src/acervo

openapi:
	uv run python scripts/export_openapi.py
	cd web && pnpm gen:api

web-check:
	cd web && pnpm install --frozen-lockfile && pnpm typecheck && pnpm lint && pnpm test && pnpm build
