# Acervo

Knowledge bases in the style of Notion, with a side chat that files what you drop in it: a PDF is saved in the right folder, a thing you learned becomes a proposed edit to the right Markdown page, and a question is answered by navigating folders and the pages of PDFs. Jev decides, the LLM writes, the person approves.

- `make up`: postgres, redis, minio, migrate and the API on http://localhost:8000; copy `.env.example` to `.env` first.
- `make test`: pytest with coverage, against real Postgres and MinIO (`docker compose up -d postgres minio`).
- `make lint`: ruff check, ruff format check, mypy.
- `make migrate`, `make revision m="add x"`: Alembic.
- `make openapi`: regenerates `docs/openapi.json` and the web client.
- `make web-check`: the web app's install, typecheck, lint, test and build; `cd web && pnpm dev` runs it on :5173 with the key in `web/.env.local`.

How the code is laid out and the rules it never breaks are in [CLAUDE.md](CLAUDE.md); the screens are on the design canvas https://claude.ai/artifact/Jjq3r6SPUZ9E4jUG7WtqGR.
