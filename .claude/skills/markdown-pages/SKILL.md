---
name: markdown-pages
description: Markdown pages in Acervo - storage and immutable versions, sections and anchors, the Patch format, provenance comments, and the descriptions every node carries for Jev. Use when touching pages, sections, versions or node descriptions.
---

# Markdown pages

A page is a Markdown file the person can read and edit. What the person types is the page's working text, saved as
they type; versions are immutable, each holding the whole file, and are cut from the working text by editing session.
A page holds sub-pages and files as a folder does. A base exports as a plain folder: pages as `.md`, PDFs as the
original files.

| Piece | File |
|---|---|
| use cases | `services/page_service.py` (read, autosave, cut, history, diff, restore, fix links on rename) |
| versions | `repositories/page_version.py` (`page_version`: whole Markdown, author `user` or `agent`, `proposal_id`, the editing span `edit_started_at`/`edit_ended_at`) |
| working text | `repositories/page_draft.py` (table `page_draft`: one per page, its `revision`, the session's `started_at`, the version it started from) |
| links | `repositories/page_link.py` (`page_link`: the `[[…]]` targets of each page's working text), parsed by `domain/links.py` |
| sections | `domain/sections.py` (parse `##` headings into anchors) |
| diff | `domain/diff.py` |
| patch | `domain/patch.py` (`Patch`, `apply`, `rebase`; F2) |
| descriptions | `node.description`, written by `TreeService`; the folder refresh is a worker job (F2) |

## Sections and anchors

A section is a `##` heading and everything until the next `##`. Its anchor is the slug of the heading
(`## Documentos` → `documentos`). Agents address pages by section, never by line number.

## Blocks

The web editor (skill `ui-web`) shows a page as blocks and writes it back as Markdown: CommonMark, GFM task lists
and tables, a callout as a GFM alert (`> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`), a toggle as
`<details><summary>…</summary>…</details>`, a page link and a sub-page as `[[Title]]`. Markdown it has no block for
stays as written. An untouched page is saved back byte-equal, so pages written by hand or by an agent keep their
form. Sections stay `##` headings: nothing the editor adds changes how a page is cut into sections.

## Sub-pages

A page is a parent like a folder: sub-pages and files live under it (`parent_id`), move with it and go to the Lixeira
and back with it. "/subpágina" creates the child and puts a `[[Title]]` link to it in the text; the page screen also
lists its children at its end, which is not stored in the Markdown. Two pages may not share a title among siblings; a
page and a folder may.

## Patch

```python
Patch(page_id, base_version, anchor, op, lines)   # op: append | insert_after | replace | new_section
```

- `append` adds lines at the end of the section; `replace` swaps a line the LLM identified by its exact text.
- Every line an agent adds is followed by a provenance comment:
  `<!-- origem: chat · 2026-10-22 · proposta 8f3a -->` (or `origem: <file>.pdf p. 14` when it came from reading a PDF).
- An agent patches the newest version, never the working text: the working text is cut as a version before an agent
  reads a page, so `base_version` is what the person last typed.
- `rebase`: when the page changed after the proposal was made, re-find the anchor in the current version; if the
  anchor or the replaced line is gone, the proposal goes back to "needs a new diff" and the LLM writes it again.

## Descriptions

Every node (folder, page, PDF) has a `description` of at most 200 characters. They are the text of Jev's options,
so placement is only as good as they are.

| Node | Description comes from |
|---|---|
| folder | LLM `describe` over its children, refreshed by a debounced job when children change |
| page | its first paragraph, else its `##` headings |
| PDF | the card made at intake |

A description the person edits is locked (`description_locked`) and never rewritten by the job.

## The person's edits

The person writes directly: their own action is their approval (skill `proposals`), and the version records author
`user`.

- **Working text.** The editor saves about a second after typing stops (`PUT /v1/pages/{id}/text` with the
  `revision` it read); each save replaces the working text and bumps its `revision`. It is not a version and never
  shows in the history. The page's text is the working text when there is one, else the newest version.
- **Versions by editing session.** A version is cut from the working text when a save comes after
  `Settings.version_idle_seconds` (300) without a change, when the person leaves the page (`POST .../leave`), and
  before anything reads the history or an agent reads the page. A cut equal to the newest version writes nothing. A
  version keeps when its session started and ended ("12 min de edição").
- **Another tab.** A save from an older `revision` is a `StalePage` (`stale_page`, 409): the refused text is kept as
  a version first and the error carries the newest `markdown` and `revision`, so the editor reloads and nothing typed
  is lost.
- **Restore** writes the old text as a new version and as the working text with a new `revision`, so an open editor
  reloads instead of overwriting it; no version is ever changed or deleted.

## Rules

- No page is created from a PDF's content. A page may link to a PDF and cite its pages; a PDF under a page is a file,
  never part of its text.
- Wiki links `[[Page name]]` resolve inside the base: with more than one page of that title, the one under the same
  parent, else the link is ambiguous. Every save of the working text rewrites its rows in `page_link`, so a rename
  finds the linking pages by index and fixes each with a new version, also set as the working text (author `user`
  when the person renamed; through a proposal when an agent did).
