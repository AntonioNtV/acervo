---
name: repo-structure
description: Where each concept of Acervo lives and which way imports go. Use to decide the folder of new code, or before reading an unfamiliar area.
---

# Repo structure

`src/acervo/` is layered. A request enters at `api/`, a service runs the use case and commits, repositories persist,
the pipeline reads PDFs.

| Folder | Owns | Start reading at |
|---|---|---|
| `core/` | `Settings` (database, S3, API key, CORS, `version_idle_seconds`, `cover_max_bytes`), the error hierarchy with its codes, id helpers (uuid7), signed links | `core/settings.py`, `core/errors.py` |
| `domain/` | pure rules with no I/O: sort keys, sections and anchors, line diffs, `[[…]]` link parsing | `domain/sections.py` |
| `schemas/` | DTOs of entities (`XCreate`, `XUpdate`, `XRead`) and of the API (`XRequest`, `XResponse`), `ErrorResponse` | `schemas/node.py` |
| `db/` | SQLAlchemy 2 `Base` with the naming convention, `UUIDPkMixin`, `TimestampMixin`, the session, one ORM file per table in `db/models/` | `db/base.py` |
| `repositories/` | `BaseRepository`, `UnitOfWork`, one repository per table (skill `repositories`) | `repositories/base.py` |
| `services/` | use cases: `BaseService` (kbs), `TreeService`, `PageService`, `FileService`, `CoverService`, `FavoriteService`, `DuplicateService`, `ExportService`, `Storage` (S3/MinIO) | `services/tree_service.py` |
| `pipeline/` | computation with no database: `pdf/reader.py` (page count, password flag) | `pipeline/pdf/reader.py` |
| `api/` | `create_app()`, deps (settings, `UnitOfWork`, services, `X-API-Key`), error handlers, one router per resource | `api/main.py` |

Outside `src/`: `migrations/` (Alembic), `tests/` (by layer, skill `testing`), `scripts/export_openapi.py`,
`docs/openapi.json` (generated, committed), `web/` (skill `ui-web`).

## Imports

```
api  >  services  >  repositories > db
                  >  pipeline
everything   >  schemas, domain, core
```

- `api/` imports `services/`, `schemas/`, `core/` and `api/deps.py`; never `db/`, `repositories/` or `pipeline/`.
  Exception, the composition roots: `api/main.py` may import `acervo.db.session` to build the engine at startup,
  and `api/deps.py` may import `acervo.repositories.uow` to open one `UnitOfWork` per request.
- `services/` never imports `db/`: it works with `schemas/` through the `UnitOfWork`.
- `pipeline/` never imports `db/`, `repositories/` or `services/`; it receives bytes or a path and returns plain
  types.
- `domain/` imports only `core/`. No SQLAlchemy, FastAPI or httpx in `core/`, `domain/`, `schemas/` or `pipeline/`.

`tests/unit/test_layering.py` walks the AST of every module and fails on an import against this list.

## Where new code goes

- A field the API returns → `schemas/`, built by a service (skill `http-api`).
- A pure rule with many cases (sorting, sections, a diff, links) → `domain/`, unit-tested in `tests/unit/`.
- Reading something out of a PDF → `pipeline/pdf/`, called by `FileService` (skill `pdf-files`).
- A rule about what may happen to a PDF or any file → `FileService` (skill `pdf-files`).
- A change to the tree, a page or a file → the service that owns it: `TreeService`, `PageService`, `FileService`.
- A table or column → `db/models/`, a repository, a migration (skill `creating-migrations`).
- A screen → skill `ui-design` first, then `ui-web`.

## Local services

```bash
cp .env.example .env
make up                # postgres :55433, minio :59000, migrate, api :8000
# or the API from source:
docker compose up -d postgres minio minio-bucket
uv sync && make migrate
uv run uvicorn acervo.api.main:app --reload
cd web && pnpm install && pnpm dev
```
