---
name: markdown-pages
description: Markdown pages in Acervo - storage and immutable versions, sections and anchors, the Patch format, provenance comments, and the descriptions every node carries for Jev. Use when touching pages, sections, versions or node descriptions.
---

# Markdown pages

A page is a Markdown file the person can read and edit. Every save is a new immutable version holding the whole
file. A base exports as a plain folder: pages as `.md`, PDFs as the original files.

| Piece | File |
|---|---|
| versions | `pages/versions.py` (`page_version`: whole Markdown, author `user` or `agent`, `proposal_id`) |
| sections | `pages/sections.py` (parse `##` headings into anchors) |
| patch | `pages/patch.py` (`Patch`, `apply`, `rebase`) |
| descriptions | `tree/descriptions.py` |

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

## Rules

- No page is created from a PDF's content. A page may link to a PDF and cite its pages.
- Wiki links `[[Page name]]` resolve inside the base; a rename updates them through a proposal.
