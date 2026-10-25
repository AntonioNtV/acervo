---
name: testing
description: How Acervo's Python tests are written and run - the test layers, real Postgres and MinIO, the fixtures and file fixtures, coverage and what to test. Use when writing or running a test in tests/.
---

# Testing

The web app's tests are in skill `ui-web`.

```bash
docker compose up -d postgres minio
make test                                  # everything CI runs, with coverage (floor 85%, pyproject.toml)
uv run pytest tests/services -k duplicate  # one area
```

Each pytest session creates its own database (migrated to head once) and its own bucket, and drops them at the
end, so worktrees running at once never meet. Each test runs in a transaction rolled back at the end: commits inside
it act on savepoints.

## Layers

| Folder | Tests | Database |
|---|---|---|
| `tests/unit/` | `domain/` and `pipeline/` rules, pure functions, signed links; `test_layering.py` | no |
| `tests/repositories/` | `BaseRepository`, each repository's own queries and the constraints they rely on | real |
| `tests/migrations/` | upgrade → downgrade → upgrade; autogenerate has no diff | real |
| `tests/services/` | use cases through a `UnitOfWork`: what is stored, what is refused | real |
| `tests/api/` | routes via `httpx.AsyncClient` on `create_app()`: statuses, `ErrorResponse` codes, the API key | real |

## Fixtures

| Fixture | File | Gives |
|---|---|---|
| `database_url`, `engine`, `session` | `tests/conftest.py` | the session's migrated database, a rolled-back session |
| `uow` | `tests/conftest.py` | a `UnitOfWork` on the test's connection, not yet entered |
| `migrations` | `tests/conftest.py` | Alembic pointed at the session's database |
| `storage`, `test_settings` | `tests/conftest.py` | the S3 settings with the session's bucket, and the API key |
| `make_tree` | `tests/conftest.py` | builds a base from a dict: `{"Bradesco": {"Residencial": ["Emissão de apólice.md", "CG 2026.pdf"]}}`; `.md` names are pages with one version, other names with an extension are files with fake metadata and no bytes; returns the nodes by path |
| `app`, `client` | `tests/api/conftest.py` | `create_app()` on the test's connection, an `httpx.AsyncClient` with `X-API-Key` |
| files | `tests/fixtures/pdfs/`, `tests/fixtures/files/` | `simple.pdf`, `protected.pdf`, `photo.png` |

## Things to assert

- Rules of `CLAUDE.md`: a file is stored byte for byte and never becomes page text; an import against the layers
  fails `test_layering.py`.
- Versions: a save after the idle time cuts one, a cut equal to the newest writes nothing, a stale save keeps the
  refused text as a version.
- Links: a rename fixes the pages linking to it; a move to another base unlinks what it would break.
- Trash: a subtree goes and comes back together; duplicates are refused with their path, trash and history included.

Lock behaviors someone observes: the API response and its code, what is stored. Test at the highest level that
shows it (service or API), and as a pure unit for rules with many cases (sort keys, sections, diffs, links). Wiring
and plain models get no test of their own. Extend the closest test file before creating one. Names and data in
English, except content that is Portuguese on purpose (page text, file names).

A change that drops coverage under the floor fails `make test`: cover the new behavior, do not lower the floor.
