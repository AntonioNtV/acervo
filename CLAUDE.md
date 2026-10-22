# Acervo

Knowledge bases in the style of Notion, with a side chat that files what you drop in it. A PDF is saved in the
right folder; a thing you learned becomes a proposed edit to the right Markdown page; a question is answered by
navigating folders and the pages of PDFs. The LLM writes, Jev decides, code applies the policy, the person approves.

- Python project at the root (package `src/acervo`, `migrations/`, `tests/`), React app in `web/`.
- Design boards: https://claude.ai/artifact/Jjq3r6SPUZ9E4jUG7WtqGR (canvas "Acervo · Interface").

## Non-negotiables

1. Dependencies go one way: `api` → `services` → (`repositories` → `db`) and (`pipeline` → `model_clients`).
   `domain`, `schemas` and `core` are leaves every layer may import. Checked by `tests/unit/test_layering.py`.
   (skill `repo-structure`)
2. Pydantic for every type that crosses a boundary. ORM objects never leave `repositories/`; repositories never
   commit, services do. (skill `repositories`)
3. **A PDF stays a PDF.** It is saved, moved, renamed or replaced by a newer version. It is never converted to
   Markdown, never becomes a page, never gets copied into one. (skill `pdf-files`)
4. **No chunks, no embeddings, no vector store.** Retrieval is navigation: descend folders, open a file, read whole
   pages. (skill `navigator-agent`)
5. **Nothing is written without the person.** Agents produce proposals; only an accepted proposal changes a base,
   through `services/proposal_service.py`. The person's own actions write through the other services. (skill
   `proposals`)
6. **Jev decides, the LLM writes, code decides what a probability means.** Thresholds live in config
   (`core/settings.py`, `Thresholds`), never in a prompt. (skills `jev-decisions`, `llm-calls`)
7. **Every decision is logged** with its options and probabilities, linked to the proposal it produced.
8. Every table change ships with an Alembic migration and passes the roundtrip test. (skill `creating-migrations`)

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
| `jev-decisions` | adding or changing a decision (route, choose, judge) |
| `llm-calls` | adding or changing something the LLM writes |
| `curator-agent` | where and how a dropped PDF or a learned fact is filed |
| `navigator-agent` | how a question is answered by navigation |
| `pdf-files` | anything that touches a PDF: upload, map, reading pages, versions |
| `markdown-pages` | pages, sections, versions, descriptions of nodes |
| `proposals` | the proposal lifecycle, diffs, accept, reject, rebase |
| `testing` | writing or running a Python test |
| `evals` | measuring placement and answers, calibrating thresholds |
| `ui-design` | designing or changing a screen |
| `ui-web` | code in `web/`: structure, checks, editor, PDF viewer, chat |

## Commands

```bash
make up                  # docker compose: postgres, redis, minio, migrate, api on :8000; copy .env.example to .env first
make migrate             # alembic upgrade head
make revision m="add x"  # alembic revision --autogenerate
make test                # pytest with coverage (floor 85%)
make lint                # ruff check, ruff format --check, mypy src/acervo
make openapi             # docs/openapi.json and web/src/api/schema.gen.ts
make web-check           # web: install, typecheck, lint, test, build
```
