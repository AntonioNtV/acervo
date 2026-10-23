.PHONY: up down migrate revision worker reindex test lint openapi web-check eval-ai1 eval-retrieval

up:
	docker compose up -d --build --wait

down:
	docker compose down

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate -m "$(m)"

worker:
	uv run arq acervo.worker.settings.WorkerSettings

# Indexes every file and page of base `kb`, for what was there before indexing; the worker builds them.
reindex:
	uv run python -m acervo.cli reindex $(kb)

test:
	uv run pytest --cov=acervo

# The AI-1 synthetic cases with the LLM decider, in a database and bucket of their own; skipped without an LLM key.
eval-ai1:
	uv run python evals/ai1/run.py

# The retrieval questions through the chat, with the configured models; skipped without an LLM key.
eval-retrieval:
	uv run python evals/retrieval/run.py

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src/acervo

openapi:
	uv run python scripts/export_openapi.py
	cd web && pnpm gen:api

web-check:
	cd web && pnpm install --frozen-lockfile && pnpm typecheck && pnpm lint && pnpm test && pnpm build
