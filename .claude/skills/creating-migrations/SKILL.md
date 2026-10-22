---
name: creating-migrations
description: How to change Acervo's tables - SQLAlchemy model, repository and an Alembic migration reviewed by hand. Use for any change to python/src/acervo/store/models.py.
---

# Creating migrations

Acervo owns the `acervo` schema and its Alembic history. `acervo db upgrade` runs `store/migrations/` to head.

## Tables

| Table | Holds |
|---|---|
| `kb` | bases |
| `node` | the tree: `kind` folder, page or pdf; `parent_id`, `title`, `description`, `description_locked`, `sort` |
| `page_version` | immutable whole Markdown per version, `author`, `proposal_id` |
| `pdf_file` | `storage_key`, `sha256`, `pages`, `doc_type`, `sensitive`, `map` (jsonb), `map_origin` |
| `pdf_file_version` | earlier files of a PDF node |
| `proposal` | `kind`, `payload`, `edited_payload`, `alternatives`, `status`, `reject_reason`, `run_id`, `base_version_id` |
| `decision_log` | `run_id`, `step`, `question_type`, `options`, `probs`, `threshold`, `action`, `latency_ms`, `cached` |

There is no table of chunks or embeddings, and none may be added (`CLAUDE.md`, rule 2).

## Steps

1. Model in `store/models.py`, subclassing `Base, TableModel` (`id`, `created_at`, `updated_at`).
2. Repository in `store/repositories.py`.
3. `uv run alembic revision --autogenerate -m "<slug>"`, then read the file and fix it by hand: names of
   constraints, server defaults, jsonb types, and a real `downgrade`.
4. Data conversion is a throwaway script, never a migration.

The MVP has one user per install. When teams come, every table gets `workspace_id` and row-level security in the
same migration; do not add it piecemeal.

## Check

```bash
cd python
uv run pytest tests/store
uv run acervo db upgrade --url postgresql://acervo:acervo@localhost:55433/<scratch db>
```
