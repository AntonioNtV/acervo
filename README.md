# Acervo

Knowledge bases a team writes and keeps together: each base is a tree of folders, pages and PDF files. Pages nest and are written in a block editor that saves itself and keeps a version per editing session; PDFs are kept as the original files, with their versions.

- `make up`: postgres, minio, migrate and the API on http://localhost:8000; copy `.env.example` to `.env` first.
- Every route asks for the `X-API-Key` header but `GET /v1/health`, open on purpose because the compose healthcheck calls it; a file's bytes also open through the 60-second link of `POST /v1/files/{id}/link`, so the key never goes in a URL.
- `make test`: pytest with coverage, against real Postgres and MinIO (`docker compose up -d postgres minio`).
- `make lint`: ruff check, ruff format check, mypy.
- `make migrate`, `make revision m="add x"`: Alembic.
- `make openapi`: regenerates `docs/openapi.json` and the web client.
- `make web-check`: the web app's install, typecheck, lint, test and build; `cd web && pnpm dev` runs it on :5173 with the key in `web/.env.local`.
- The app: a sidebar with every base and its favorites; pages that nest, with icons, covers, `@` mentions and `[[links]]`; folder and PDF screens; ⌘K search; a trash; export and duplicate.

How the code is laid out and the rules it never breaks are in [CLAUDE.md](CLAUDE.md).
