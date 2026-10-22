---
name: creating-migrations
description: How to change Acervo's tables - SQLAlchemy 2 model, schemas, repository and an Alembic migration that round-trips. Use for any change to src/acervo/db/models/.
---

# Creating migrations

Acervo owns the `acervo` schema and its Alembic history. Alembic's async `migrations/env.py` reads `Base.metadata`
and `Settings.database_url`. The compose service `migrate` runs `alembic upgrade head` before `api` starts.
Exemplar: `migrations/versions/0001_initial.py`.

## Tables

| Table | Holds |
|---|---|
| `kb` | bases; `deleted_at` while the base is in the global trash |
| `node` | the tree: `kind` folder, page or file; `parent_id` (null at the root), `title` (a file's keeps its extension), `description`, `description_locked`, `sort` (fractional index), `deleted_at`, `trashed_with` (the node whose trashing hid this one) |
| `page_version` | immutable whole Markdown per version, `author` (`user` or `agent`), `proposal_id`, `edit_started_at`/`edit_ended_at` (set when cut from an editing session) |
| `page_draft` | the page's working text: `markdown`, `revision`, `started_at` (the editing session), `base_version_id`; versions are cut from it (skill `markdown-pages`) |
| `page_link` | `[[…]]` links: `from_node_id` and the normalized `target` title, to fix links on rename |
| `file` | the current file of a `file` node: `storage_key`, `sha256`, `size`, `mime`, `pages`, `protected`, `doc_type`, `sensitive`, `map` (jsonb), `map_origin` |
| `file_version` | earlier files of a `file` node, same columns plus `replaced_at` |
| `proposal` | `kind`, `payload`, `edited_payload`, `alternatives`, `status`, `reject_reason`, `run_id`, `base_version_id` |
| `decision_log` | `run_id`, `step`, `question_type`, `options`, `probs`, `threshold`, `action`, `latency_ms`, `cached` |

There is no table of chunks or embeddings, and none may be added (`CLAUDE.md`, no chunks, no embeddings).

Two siblings that are alive cannot share a title: a unique index on (`kb_id`, parent, `kind`, `lower(title)`) where
`deleted_at is null`, with nulls not distinct so the root counts as a parent. A trigram index on
`acervo.immutable_unaccent(lower(title))` serves the person's name filter only (skill `navigator-agent`).

Trashing marks the whole subtree with `deleted_at` and the trashed root's id in `trashed_with`; restore unmarks by
that id. Every query of live nodes filters `deleted_at is null`.

## Steps

1. **Model** in `db/models/<table>.py`: `class X(UUIDPkMixin, TimestampMixin, Base)` with `Mapped[...]` and
   `mapped_column`, registered in `db/models/__init__.py`. ORM classes have plain names (`Kb`, `Node`, `File`).
   New rows get uuid7 ids; rows already stored keep their uuid4.
2. **Constraints** named by the metadata naming convention in `db/base.py` (`uq_`, `fk_`, `ix_`, `pk_`). The names
   already stored must not change: migration 0001 used the same convention.
3. **Schemas and repository** (skill `repositories`).
4. **Migration:** `make revision m="add x"` runs `alembic revision --autogenerate`. Treat the output as a draft:
   - check partial indexes (`postgresql_where`), expression indexes (autogenerate cannot compare
     `ix_node_title_trgm`), server defaults and JSONB columns by hand;
   - name the file `NNNN_<slug>.py`, the next number, with `revision = "NNNN"` and `down_revision` the previous;
   - write a real `downgrade` that undoes the upgrade.
5. **Data changes** (backfills) are a separate script in `scripts/`, never inside a migration.

The MVP has one user per install. When teams come, every table gets `workspace_id` and row-level security in the
same migration; do not add it piecemeal.

## Check

```bash
make migrate
uv run pytest tests/migrations       # upgrade head → downgrade base → upgrade head on the session's database,
                                     # then autogenerate must report no difference against the ORM
uv run pytest tests/repositories -k <x>
```
