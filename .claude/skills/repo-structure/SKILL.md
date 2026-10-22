---
name: repo-structure
description: Where each concept of Acervo lives and which way imports go. Use to decide the folder of new code, or before reading an unfamiliar area.
---

# Repo structure

Two apps: `python/` (the API, the agents and the jobs, package `acervo`) and `web/` (the React app, skill `web-app`).
The Python package is laid out by concept, one level deep. A concept owns its models, its logic and its storage
access; there are no layers (no controller → service → repository chain).

| Folder / file in `python/src/acervo/` | Owns | Start reading at |
|---|---|---|
| `config.py` | settings and `Thresholds` (every cut-off a probability is compared to) | `config.py` |
| `errors.py` | every error with its HTTP status | `errors.py` |
| `tree/` | the node tree of a base: folders, pages, files, paths, moves, renames, trash, node descriptions | `tree/nodes.py` |
| `pages/` | Markdown pages: versions, sections and anchors, patches | `pages/patch.py` |
| `pdfs/` | uploaded files, PDFs and any other type: storage, hashing, file versions; for PDFs the section map and reading pages as text or image | `pdfs/reader.py`, `pdfs/map.py` |
| `decide/` | the `Decider` protocol, `JevDecider`, `LlmDecider`, the decision log, the response cache | `decide/decider.py` |
| `llm/` | the `Writer`: every call that generates text, its prompts in `llm/prompts/*.md` | `llm/writer.py` |
| `proposals/` | proposal models, the lifecycle, accept (apply), reject, rebase | `proposals/lifecycle.py` |
| `curator/` | the agent that files things: the card of an input, the descent, the policy, building proposals | `curator/curator.py` |
| `navigator/` | the agent that answers: tools, the loop, the budget, citations | `navigator/loop.py` |
| `store/` | SQLAlchemy models, repositories, Alembic migrations | `store/models.py` |
| `jobs/` | the worker and its jobs (PDF intake, description refresh, weekly tidy-up) | `jobs/worker.py` |
| `api/` | FastAPI app, routes, request/response models, the websocket | `api/app.py`, `api/routes.py` |
| `cli.py` | `acervo db upgrade`, `acervo worker`, `acervo contract schemas`, `acervo evals …` | |

`python/tests/` mirrors these folders. `python/evals/` holds the golden sets (skill `evals`).

## Where new code goes

- A new kind of decision → a question builder in the concept that asks it (`curator/questions.py`,
  `navigator/questions.py`), sent through a `Decider` (skill `jev-decisions`). Never a direct HTTP call to Jev.
- Something the LLM writes → a method on `Writer` and a prompt file (skill `llm-calls`).
- A rule about what may happen to a PDF or any file → `pdfs/` and the allowed proposal kinds (skill `pdf-files`).
- Anything an agent changes in a base → a proposal kind and its `apply` in `proposals/apply.py` (skill
  `proposals`). The person's own actions write directly through `tree/`, `pages/` and `pdfs/`, the same functions
  `apply.py` calls.
- A table or column → `store/models.py` and a migration (skill `creating-migrations`).
- Something the UI calls → a route in `api/routes.py` (skill `http-contract`).

## Imports

Imports go down this list, never up. `uv run lint-imports` (CI) fails on one that goes against it.

```
cli > api > jobs > (curator : navigator) > proposals
  > (decide : llm : pages : pdfs : tree) > store > (config : errors)
```

Modules inside a parenthesis do not import each other. `curator` and `navigator` share nothing but what sits below
them. `decide` and `llm` never import `pages`, `pdfs` or `tree`: the agent builds the state and hands it down.
A type two tiers share lives in the lower one.

## Local services

```bash
docker compose up -d     # Postgres :55433, Redis :56379, MinIO :59000 (PDF storage)
cd python && uv sync
uv run acervo db upgrade
uv run uvicorn acervo.api.app:app --reload
uv run acervo worker
cd ../web && pnpm install && pnpm dev
```
