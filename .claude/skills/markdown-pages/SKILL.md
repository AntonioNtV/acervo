---
name: markdown-pages
description: Markdown pages in Acervo - storage and immutable versions, sections and anchors, the Patch format, provenance comments, and the descriptions every node carries for Jev. Use when touching pages, sections, versions or node descriptions.
---

# Markdown pages

A page is a Markdown file the person can read and edit. Every save is a new immutable version holding the whole
file. A base exports as a plain folder: pages as `.md`, PDFs as the original files.

| Piece | File |
|---|---|
| use cases | `services/page_service.py` (read, save, drafts, history, diff, restore, fix links on rename) |
| versions | `repositories/page_version.py` (`page_version`: whole Markdown, author `user` or `agent`, `proposal_id`) |
| drafts | `repositories/page_draft.py` (`page_draft`: one per page, with the version it started from) |
| links | `repositories/page_link.py` (`page_link`: the `[[…]]` targets of each page's current version), parsed by `domain/links.py` |
| sections | `domain/sections.py` (parse `##` headings into anchors) |
| diff | `domain/diff.py` |
| patch | `domain/patch.py` (`Patch`, `apply`, `rebase`; F2) |
| descriptions | `node.description`, written by `TreeService`; the folder refresh is a worker job (F2) |

## Sections and anchors

A section is a `##` heading and everything until the next `##`. Its anchor is the slug of the heading
(`## Documentos` → `documentos`). Agents address pages by section, never by line number.

## Patch

```python
Patch(page_id, base_version, anchor, op, lines)   # op: append | insert_after | replace | new_section
```

- `append` adds lines at the end of the section; `replace` swaps a line the LLM identified by its exact text.
- Every line an agent adds is followed by a provenance comment:
  `<!-- origem: chat · 2026-10-22 · proposta 8f3a -->` (or `origem: <file>.pdf p. 14` when it came from reading a PDF).
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
`user`. While editing, a draft is saved every few seconds in `page_draft`; it is not a version, never shows in the
history and is never read by agents. "Concluir" writes a new version only if the text differs from the current one,
and only if the current version is still the draft's base version: otherwise it is a `StalePage` (`stale_page`) with
the difference, and the person keeps theirs (a new version on top) or discards it. Restoring an old version writes it as
a new version; no version is ever changed or deleted.

## Rules

- No page is created from a PDF's content. A page may link to a PDF and cite its pages.
- Wiki links `[[Page name]]` resolve inside the base: with more than one page of that title, the one in the same
  folder, else the link is ambiguous. Every new version rewrites its rows in `page_link`, so a rename finds the
  linking pages by index and fixes each with a new version (author `user` when the person renamed; through a
  proposal when an agent did).
