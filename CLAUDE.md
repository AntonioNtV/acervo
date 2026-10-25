# Acervo

Knowledge bases a team writes and keeps together. Each base is a tree of folders, pages and PDF files: pages nest,
are written in a block editor that saves itself and keep a version per editing session; PDFs are kept as the
original files, with their own versions. Search finds any page, folder or file by its title.

- Python project at the root (package `src/acervo`, `migrations/`, `tests/`), React app in `web/`.

## Non-negotiables

1. Dependencies go one way: `api` → `services` → `repositories` → `db`, and `services` → `pipeline` (pure
   computation, such as reading a PDF). `domain`, `schemas` and `core` are leaves every layer may import. Checked by
   `tests/unit/test_layering.py`. (skill `repo-structure`)
2. Pydantic for every type that crosses a boundary. ORM objects never leave `repositories/`; repositories never
   commit, services do. (skill `repositories`)
3. **A PDF stays a PDF.** It is saved, moved, renamed or replaced by a newer version. It is never converted to
   Markdown, never becomes a page, never gets copied into one. (skill `pdf-files`)
4. **A page's history is kept.** Every saved version of a page and every replaced version of a file stays; restoring
   one writes a new version, it never rewrites the old ones. (skills `markdown-pages`, `pdf-files`)
5. Every table change ships with an Alembic migration and passes the roundtrip test. (skill `creating-migrations`)

## Conventions

- Every non-trivial change follows skill `feature-flow`: interview, spec ✋, cards ✋, `senior-engineer` agents in
  worktrees, `ponytail:ponytail-review` and the `reviewer` agent. No code before the cards are approved.
- Code, identifiers, commits, tests and skills in English. Text the person reads in the app is pt-BR (i18n).
- A comment only for the why the code does not show. No new markdown files besides skills and `README.md`.
- `.work/` holds the feature flow's files and never goes into git.
- Conventional Commits: `feat(<area>): …`, `fix(<area>): …`.

## Agents (`.claude/agents/`)

- `senior-engineer`: implements one approved card in its own worktree (feature-flow step 5).
- `reviewer`: clean-context review of the integrated diff against spec and cards (feature-flow step 6).

The flow also uses the `ponytail` plugin (`ponytail:ponytail` full, `ponytail:ponytail-review`).

## Skills (`.claude/skills/`)

| Skill | Use when |
|---|---|
| `feature-flow` | any non-trivial change: interview, spec, cards, parallel implementation, review |
| `repo-structure` | deciding where new code goes, or reading an unfamiliar area |
| `http-api` | a route, a request/response model, an error code, the generated client |
| `repositories` | reading or writing the database from a service |
| `creating-migrations` | any change to `src/acervo/db/models/` |
| `pdf-files` | anything that touches a PDF: upload, reading pages, versions |
| `markdown-pages` | pages, sections, versions, links, descriptions of nodes |
| `testing` | writing or running a Python test |
| `ui-design` | designing or changing a screen |
| `ui-web` | code in `web/`: structure, checks, editor, PDF viewer |

## Commands

```bash
make up                  # docker compose: postgres, minio, migrate, api on :8000; copy .env.example to .env first
make migrate             # alembic upgrade head
make revision m="add x"  # alembic revision --autogenerate
make test                # pytest with coverage (floor 85%)
make lint                # ruff check, ruff format --check, mypy src/acervo
make openapi             # docs/openapi.json and web/src/api/schema.gen.ts
make web-check           # web: install, typecheck, lint, test, build
```
