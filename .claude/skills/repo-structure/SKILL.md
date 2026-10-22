---
name: repo-structure
description: Where each concept of Acervo lives and which way imports go. Use to decide the folder of new code, or before reading an unfamiliar area.
---

# Repo structure

`src/acervo/` is layered. A request (or, from F2, a job) enters at `api/` (or `worker/`), a service runs the use
case and commits, repositories persist, the pipeline computes, model clients call Jev and the LLM.

| Folder | Owns | Start reading at |
|---|---|---|
| `core/` | `Settings` with `Thresholds` and `NavigatorBudget` (every cut-off a probability is compared to), the error hierarchy with its codes, id helpers (uuid7) | `core/settings.py`, `core/errors.py` |
| `domain/` | pure rules with no I/O: sort keys, sections and anchors, diffs, `[[…]]` link parsing; from F2 the `Patch`, the PDF section map and Jev's `Noul` / `Choice` / `Score` | `domain/sections.py` |
| `schemas/` | DTOs of entities (`XCreate`, `XUpdate`, `XRead`) and of the API (`XRequest`, `XResponse`), `Paginated[T]`, `ErrorResponse` | `schemas/node.py` |
| `db/` | SQLAlchemy 2 `Base` with the naming convention, `UUIDPkMixin`, `TimestampMixin`, the session, one ORM file per table in `db/models/` | `db/base.py` |
| `repositories/` | `BaseRepository`, `UnitOfWork`, one repository per table (skill `repositories`) | `repositories/base.py` |
| `services/` | use cases: `BaseService` (kbs), `TreeService`, `PageService`, `FileService`, `Storage` (S3/MinIO); from F2 `ProposalService`, the only apply | `services/tree_service.py` |
| `pipeline/` | computation with no database: `pdf/reader.py` (page count, password flag); from F2 `pipeline/curator/`, `pipeline/navigator/`, the PDF map | `pipeline/pdf/reader.py` |
| `model_clients/` | from F2: the `Decider` protocol with `JevDecider`, `LlmDecider` and a fake; the `Writer` (every call that generates text) and its prompts | |
| `api/` | `create_app()`, deps (settings, `UnitOfWork`, services, `X-API-Key`), error handlers, one router per resource | `api/main.py` |
| `worker/` | from F2: the worker loop and its jobs (PDF intake, description refresh, weekly tidy-up) | |

Outside `src/`: `migrations/` (Alembic), `tests/` (by layer, skill `testing`), `scripts/export_openapi.py`,
`docs/openapi.json` (generated, committed), `web/` (skill `ui-web`), `evals/` from F2 (skill `evals`).

## Imports

```
api, worker  >  services  >  repositories > db
                          >  pipeline > model_clients
everything   >  schemas, domain, core
```

- `api/` imports `services/`, `schemas/`, `core/` and `api/deps.py`; never `db/`, `repositories/`, `pipeline/` or
  `model_clients/`. Exception, the composition roots: `api/main.py` may import `acervo.db.session` to build the
  engine at startup, and `api/deps.py` may import `acervo.repositories.uow` to open one `UnitOfWork` per request.
- `services/` never imports `db/`: it works with `schemas/` through the `UnitOfWork`.
- `pipeline/` never imports `db/`, `repositories/` or `services/`; it receives clients and state, returns domain
  types. The Curator and the Navigator build state and hand it down: `model_clients/` never sees a repository.
- `model_clients/` imports only `domain/` and `core/`.
- `domain/` imports only `core/`. No SQLAlchemy, FastAPI or httpx in `core/`, `domain/`, `schemas/` or `pipeline/`.

`tests/unit/test_layering.py` walks the AST of every module and fails on an import against this list.

## Where new code goes

- A field the API returns → `schemas/`, built by a service (skill `http-api`).
- A pure rule with many cases (sorting, sections, a diff, a patch) → `domain/`, unit-tested in `tests/unit/`.
- A new kind of decision → a question builder next to the agent that asks it (`pipeline/curator/questions.py`,
  `pipeline/navigator/questions.py`), sent through a `Decider` (skill `jev-decisions`). Never a direct HTTP call to
  Jev outside `model_clients/`.
- Something the LLM writes → a method on `Writer` and a prompt file in `model_clients/` (skill `llm-calls`).
- A rule about what may happen to a PDF or any file → `FileService` and the allowed proposal kinds (skill
  `pdf-files`).
- Anything an agent changes in a base → a proposal kind and its apply in `services/proposal_service.py` (skill
  `proposals`). The person's own actions go through `TreeService`, `PageService` and `FileService`, the same
  methods the proposal service calls.
- A table or column → `db/models/`, a repository, a migration (skill `creating-migrations`).
- An async operation → a job in `worker/` (from F2).
- A screen → skill `ui-design` first, then `ui-web`.

## Local services

```bash
cp .env.example .env
make up                # postgres :55433, redis :56379, minio :59000, migrate, api :8000
# or the API from source:
docker compose up -d postgres redis minio minio-bucket
uv sync && make migrate
uv run uvicorn acervo.api.main:app --reload
cd web && pnpm install && pnpm dev
```
