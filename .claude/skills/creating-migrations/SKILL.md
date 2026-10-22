---
name: creating-migrations
description: How to change Acervo's tables - SQLAlchemy model, repository and an Alembic migration reviewed by hand. Use for any change to src/acervo/store/models.py.
---

# Creating migrations

Acervo owns the `acervo` schema and its Alembic history. `acervo db upgrade` runs `store/migrations/` to head.

## Tables

| Table | Holds |
|---|---|
| `kb` | bases; `deleted_at` while the base is in the global trash |
| `node` | the tree: `kind` folder, page or file; `parent_id` (null at the root), `title` (a file's keeps its extension), `description`, `description_locked`, `sort` (fractional index), `deleted_at`, `trashed_with` (the node whose trashing hid this one) |
| `page_version` | immutable whole Markdown per version, `author` (`user` or `agent`), `proposal_id` |
| `page_draft` | one unsaved draft per page, with its `base_version_id`; never in the history, never seen by agents |
| `page_link` | `[[…]]` links: `from_node_id` and the normalized `target` title, to fix links on rename |
| `file` | the current file of a `file` node: `storage_key`, `sha256`, `size`, `mime`, `pages`, `protected`, `doc_type`, `sensitive`, `map` (jsonb), `map_origin` |
| `file_version` | earlier files of a `file` node, same columns plus `replaced_at` |
| `proposal` | `kind`, `payload`, `edited_payload`, `alternatives`, `status`, `reject_reason`, `run_id`, `base_version_id` |
| `decision_log` | `run_id`, `step`, `question_type`, `options`, `probs`, `threshold`, `action`, `latency_ms`, `cached` |

There is no table of chunks or embeddings, and none may be added (`CLAUDE.md`, rule 2).

Two siblings that are alive cannot share a title: a unique index on (`kb_id`, parent, `kind`, `lower(title)`) where
`deleted_at is null`, with nulls not distinct so the root counts as a parent. A trigram index on
`acervo.immutable_unaccent(lower(title))` serves the person's name filter only (skill `navigator-agent`).

Trashing marks the whole subtree with `deleted_at` and the trashed root's id in `trashed_with`; restore unmarks by
that id. Every query of live nodes filters `deleted_at is null`.

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
# from the repository root
uv run pytest tests/store
uv run acervo db upgrade --url postgresql://acervo:acervo@localhost:55433/<scratch db>
```
