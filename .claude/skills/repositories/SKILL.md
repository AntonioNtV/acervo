---
name: repositories
description: How Acervo reads and writes Postgres - the generic BaseRepository, the UnitOfWork, the concrete repositories and the per-base write lock. Use when a service needs data, or when adding a repository or a query.
---

# Repositories

Every database access goes through a repository. `BaseRepository[OrmT, ReadT, CreateT, UpdateT]`
(`repositories/base.py`) implements CRUD once; a concrete repository declares its four types and adds only its own
queries. Repositories take and return Pydantic models; the ORM object never leaves them.
Exemplar: `repositories/node.py`.

## BaseRepository

| Method | Behavior |
|---|---|
| `get(id)` | `NotFoundError` when missing |
| `get_by(**filters)` | equality on columns |
| `count(filters)` | |
| `create(data, **extra)`, `create_many(items)` | flush to get ids; no commit |
| `update(id, data)` | only the fields set on `data`; an empty update emits no SQL |

Only what a caller uses is there; add a generic method (pdflab's `list`, `paginate`, `exists`, `delete`) with its
first caller.

Rules: no `commit` inside a repository; an unknown filter column → `ValidationError`; `IntegrityError` on
a unique constraint → `ConflictError` naming the constraint in `details`. Rows are always live unless the query
says otherwise: every query of live nodes filters `deleted_at is null`.

## UnitOfWork

```python
async with UnitOfWork(session_factory) as uow:
    await uow.kbs.lock(kb_id)
    node = await uow.nodes.create(NodeCreate(...))
    await uow.page_versions.add(PageVersionCreate(...))
    await uow.commit()
```

| Attribute | Repository |
|---|---|
| `kbs` | `KbRepository`: `lock`, `get_in` (live or trashed), `summaries` (counts, last edit), `trashed` |
| `nodes` | `NodeRepository`: `paths`, `live_parent` (a live folder or page of the base), `title_taken`, `children` (with `has_children`), `ancestors`, sort keys, `trash_subtree`, `restore_trashed_with`, `trash_roots` |
| `files`, `file_versions` | the current file of a `file` node and its history |
| `page_versions`, `page_drafts`, `page_links` | immutable versions, the one working text per page (with its `revision`), the `[[…]]` targets |

One `UnitOfWork` per HTTP request (`api/deps.py:get_uow`); the service calls `commit()` at the end of the use case,
and an exception rolls everything back. From F2 the worker opens one per job step, so a failure late in a job keeps
what earlier steps saved, and the decision log gets its repository on the same `UnitOfWork`.

## The per-base lock

A service that checks and then writes ("já existe", a free sort key, a duplicate file) first calls
`uow.kbs.lock(kb_id)`: one writer per base until the transaction ends, so the check still holds at the write.
Keep it; the unique indexes are the last line, not the first.

## Adding a repository or a query

1. ORM model in `db/models/<table>.py` and a migration (skill `creating-migrations`).
2. `XCreate`, `XUpdate`, `XRead` in `schemas/<x>.py`; `XRead` has `model_config = ConfigDict(from_attributes=True)`.
3. `class XRepository(BaseRepository[X, XRead, XCreate, XUpdate])` with `orm_model` and `read_schema`.
4. Register it as an attribute of `UnitOfWork`.
5. Tests in `tests/repositories/` against real Postgres: the new queries and any constraint they rely on.

A query that only filters by equality uses `get_by` / `list`; write a method only when it needs a join, an
aggregate, a recursive CTE (paths, subtrees), a lock or a JSONB path. SQL expressions shared by several queries
(`sort_key`, `siblings`, `folded`) are module functions next to the repository that uses them.
