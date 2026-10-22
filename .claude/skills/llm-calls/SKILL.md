---
name: llm-calls
description: Every call in Acervo that generates text - the Writer, its roles and models, prompt files, structured output and what the LLM must never decide. Use when adding or changing something the LLM writes.
---

# LLM calls

The LLM writes what a person reads. It does not choose folders, judge relevance or decide when to stop: those are
Jev decisions (skill `jev-decisions`).

| Piece | File | What it is |
|---|---|---|
| writer | `model_clients/writer.py` | the `Writer` protocol and its client: one method per role, typed input and output |
| prompts | `model_clients/prompts/<role>.md` | the prompt of each role, in pt-BR, with `{placeholders}` |
| models | `core/settings.py` (`LlmRoles`) | which model serves each role |
| vision | `model_clients/vision.py` | reading a PDF page image (tables, scanned pages) |
| fake | `model_clients/fakes.py` | `FakeWriter`: fixed outputs per role, records inputs (skill `testing`) |

Inputs and outputs are `domain/` types; the pipeline calls the `Writer`, never a service or the database.

## Roles

| Role | Input | Output | Model |
|---|---|---|---|
| `card` | a chat message, or the first pages and the outline of a PDF | `Card`: title, one-line subject, entities, key facts, suggested file name | small |
| `describe` | a folder's children and their descriptions | a description of at most 200 characters | small |
| `pdf_map` | page titles detected on each page, when the PDF has no bookmarks and no table of contents | a list of sections with page ranges | small |
| `patch` | the page's Markdown, the section anchor, the decided action, the card | a `Patch` (skill `markdown-pages`) | strong |
| `split_question` | a question Jev flagged as two-part | sub-questions | small |
| `read_pages` | the question and the text (or images) of the pages opened | the passages that answer, with page numbers | strong, vision |
| `answer` | the question and the kept passages | the answer with citation markers | strong |
| `explain` | the logged probabilities of a proposal | one sentence: why here | small |

Small roles are where the models from the PDF extraction lab can be plugged in.

## Rules

- **Structured output** for every role but `answer`: a Pydantic model, validated; a response that fails validation
  is retried once, then the job fails with the raw response logged.
- **The LLM never sees a threshold** and is never asked "should we…?".
- **Never turn a PDF into Markdown.** `read_pages` returns passages for one answer; they are not stored as a page.
  (skill `pdf-files`)
- **Answers cite or say they did not find.** `answer` gets only the kept passages and must put a marker on every
  claim; the claims are then checked one by one (skill `navigator-agent`).
- Prompts are files, not strings in code. A prompt change is reviewed like code and rerun against its golden set.
- Personal data (CPF, names in policies) is masked before any text leaves the server when the source is marked
  `sensitive`.
