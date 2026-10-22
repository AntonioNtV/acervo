---
name: testing
description: How Acervo's Python tests are written and run - the test layers, real Postgres and MinIO, the fake Decider and Writer, PDF fixtures, coverage and what to test. Use when writing or running a test in tests/.
---

# Testing

The web app's tests are in skill `ui-web`. Quality of placement and answers is measured by `evals`, not by tests.

```bash
docker compose up -d postgres minio
make test                                  # everything CI runs, with coverage (floor 85%, pyproject.toml)
uv run pytest tests/services -k duplicate  # one area
```

Each pytest session creates its own database (migrated to head once) and its own bucket, and drops them at the
end, so worktrees running at once never meet. Each test runs in a transaction rolled back at the end: commits inside
it act on savepoints. Jev and the LLM are never called from tests: they are replaced by fakes.

## Layers

| Folder | Tests | Database | Models |
|---|---|---|---|
| `tests/unit/` | `domain/` and `pipeline/` rules, pure functions; `test_layering.py` | no | fakes |
| `tests/repositories/` | `BaseRepository`, each repository's own queries and the constraints they rely on | real | — |
| `tests/migrations/` | upgrade → downgrade → upgrade; autogenerate has no diff | real | — |
| `tests/services/` | use cases through a `UnitOfWork`: what is stored, what is refused | real | fakes |
| `tests/api/` | routes via `httpx.AsyncClient` on `create_app()`: statuses, `ErrorResponse` codes, the API key | real | fakes |
| `tests/pipeline/` (F2) | the Curator and the Navigator with `FakeDecider` and `FakeWriter` | no | fakes |

## Fixtures

| Fixture | File | Gives |
|---|---|---|
| `database_url`, `engine`, `session` | `tests/conftest.py` | the session's migrated database, a rolled-back session |
| `uow` | `tests/conftest.py` | a `UnitOfWork` on the test's connection, not yet entered |
| `migrations` | `tests/conftest.py` | Alembic pointed at the session's database |
| `storage`, `test_settings` | `tests/conftest.py` | the S3 settings with the session's bucket, and the API key |
| `make_tree` | `tests/conftest.py` | builds a base from a dict: `{"Bradesco": {"Residencial": ["Emissão de apólice.md", "CG 2026.pdf"]}}`; `.md` names are pages with one version, other names with an extension are files with fake metadata and no bytes; returns the nodes by path |
| `app`, `client` | `tests/api/conftest.py` | `create_app()` on the test's connection, an `httpx.AsyncClient` with `X-API-Key` |
| `fake_decider`, `fake_writer` (F2) | `tests/conftest.py`, from `model_clients/fakes.py` | `FakeDecider` answers from a table `{question_id: probs}` and records what was asked; `FakeWriter` gives fixed outputs per role and records inputs |
| files | `tests/fixtures/pdfs/`, `tests/fixtures/files/` | `simple.pdf`, `protected.pdf`, `photo.png`; F3 adds the map fixtures (bookmarks, table of contents, no outline, scanned) |

## Things to assert

- Policy: each side of each threshold, with `FakeDecider` (skill `jev-decisions`).
- Rules of `CLAUDE.md`: a PDF proposal never targets a page; applying any proposal never writes PDF text to a page;
  no write happens before accept; an import against the layers fails `test_layering.py`.
- That the decider got one call per state (batching), by reading `fake_decider.calls`.
- Rebase: accept after the page changed; accept after the anchor was deleted (becomes `stale`).
- The map: one test per `map_origin`, on the fixture PDFs.

Lock behaviors someone observes: the API response and its code, what is stored, the proposal produced. Test at the
highest level that shows it (service or API), and as a pure unit for rules with many cases (sort keys, sections,
diffs, links). Wiring and plain models get no test of their own. Extend the closest test file before creating one.
Names and data in English, except content that is Portuguese on purpose (page text, file names). Wait for jobs by
polling their status, never `asyncio.sleep`.

A change that drops coverage under the floor fails `make test`: cover the new behavior, do not lower the floor.
