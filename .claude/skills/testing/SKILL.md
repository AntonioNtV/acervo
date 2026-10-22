---
name: testing
description: How Acervo's Python tests are written and run - real Postgres and MinIO, the fake Decider and Writer, PDF fixtures and what to test. Use when writing or running a test in tests/.
---

# Testing

The web app's tests are in skill `web-app`. Quality of placement and answers is measured by `evals`, not by tests.

```bash
docker compose up -d
# from the repository root
uv run pytest
uv run pytest tests/curator -k conflict
```

Each session creates its own database and bucket and drops them at the end. The database and storage are real.
Jev and the LLM are never called from tests: they are replaced by fakes.

## Fixtures

| Fixture | File | Gives |
|---|---|---|
| `session` | `tests/conftest.py` | a migrated database, rolled back after the test |
| `make_tree` | `tests/conftest.py` | builds a base from a dict: `{"Bradesco": {"Residencial": ["Emissão de apólice.md", "CG 2026.pdf"]}}`; `.md` names are pages with one version, other names with an extension are files with fake metadata and no bytes; returns the nodes by path |
| `storage` | `tests/conftest.py` | the S3 settings with this session's bucket |
| `fake_decider` | `tests/decide/fakes.py` | `FakeDecider`, answers from a table `{question_id: probs}`; records what was asked |
| `fake_writer` | `tests/llm/fakes.py` | `FakeWriter`, fixed outputs per role; records inputs |
| PDFs | `tests/fixtures/pdfs/` | `with_bookmarks.pdf`, `with_toc_page.pdf`, `no_outline.pdf`, `scanned.pdf`, `two_versions/` |

## Things to assert

- Policy: each side of each threshold, with `FakeDecider` (skill `jev-decisions`).
- Rules of `CLAUDE.md`: a PDF proposal never targets a page; applying any proposal never writes PDF text to a page;
  no write happens before accept.
- That the decider got one call per state (batching), by reading `fake_decider.calls`.
- Rebase: accept after the page changed; accept after the anchor was deleted (becomes `stale`).
- The map: one test per `map_origin`, on the fixture PDFs.

Test at the highest level that shows the behavior: the agent (`tests/curator/`, `tests/navigator/`) or the API
(`tests/api/`). Names and data in English, except content that is Portuguese on purpose (page text, file names).
Wait for jobs with `poll_until`, never `asyncio.sleep`.
