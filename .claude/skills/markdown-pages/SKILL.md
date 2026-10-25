---
name: markdown-pages
description: Markdown pages in Acervo - the working text and autosave, immutable versions cut by editing session, sections and anchors, blocks, sub-pages, [[links]] and mentions, duplicate and export. Use when touching pages, sections, versions, links or node descriptions.
---

# Markdown pages

A page is a Markdown file the person can read and edit. What the person types is the page's working text, saved as
they type; versions are immutable, each holding the whole file, and are cut from the working text by editing session.
A page holds sub-pages and files as a folder does. A page or folder exports as a zip: pages as `.md`, files as the
original bytes.

| Piece | File |
|---|---|
| use cases | `services/page_service.py` (read, autosave, cut, history, diff, restore, mentions, fix links on rename, unlink on a move to another base) |
| versions | `repositories/page_version.py` (`page_version`: whole Markdown, the editing span `edit_started_at`/`edit_ended_at`) |
| working text | `repositories/page_draft.py` (table `page_draft`: one per page, its `revision`, the session's `started_at`) |
| links | `repositories/page_link.py` (`page_link`: the `[[…]]` targets of each page's working text), parsed by `domain/links.py` |
| sections | `domain/sections.py` (parse `##` headings into anchors) |
| diff | `domain/diff.py` (line diff between two versions) |
| duplicate | `services/duplicate_service.py` ("<título> (cópia)" right after the page, with its sub-pages; files are not copied) |
| export | `services/export_service.py` (a page as `<título>.md` with its children in `<título>/`) |
| descriptions | `node.description`, written by the person through `TreeService.edit` |

## Sections and anchors

A section is a `##` heading and everything until the next `##`. Its anchor is the slug of the heading
(`## Documentos` → `documentos`). `GET /v1/pages/{id}` returns the sections with the text.

## Blocks

The web editor (skill `ui-web`) shows a page as blocks and writes it back as Markdown: CommonMark, GFM task lists
and tables, a callout as a GFM alert (`> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`), a toggle as
`<details><summary>…</summary>…</details>`, a page link, a mention and a sub-page as `[[Title]]`. Markdown it has no
block for stays as written. An untouched page is saved back byte-equal, so pages written by hand keep their form.
Sections stay `##` headings: nothing the editor adds changes how a page is cut into sections.

## Sub-pages

A page is a parent like a folder: sub-pages and files live under it (`parent_id`), move with it and go to the Lixeira
and back with it. "/subpágina" creates the child and puts a `[[Title]]` link to it in the text; the page screen also
lists its children at its end, which is not stored in the Markdown. Two pages may not share a title among siblings; a
page and a folder may.

## The person's edits

- **Working text.** The editor saves about a second after typing stops (`PUT /v1/pages/{id}/text` with the
  `revision` it read); each save replaces the working text and bumps its `revision`. It is not a version and never
  shows in the history. The page's text is the working text when there is one, else the newest version.
- **Versions by editing session.** A version is cut from the working text when a save comes after
  `Settings.version_idle_seconds` (300) without a change, when the person leaves the page (`POST .../leave`), and
  before anything reads the history. A cut equal to the newest version writes nothing. A version keeps when its
  session started and ended ("12 min de edição").
- **Another tab.** A save from an older `revision` is a `StalePage` (`stale_page`, 409): the refused text is kept as
  a version first and the error carries the newest `markdown` and `revision`, so the editor reloads and nothing typed
  is lost.
- **Restore** writes the old text as a new version and as the working text with a new `revision`, so an open editor
  reloads instead of overwriting it; no version is ever changed or deleted.

## Links and mentions

- `[[Page name]]` (typed as `[[` or `@` in the editor) resolves inside the base: with more than one page of that
  title, the one under the same parent, else the link is ambiguous. Every save of the working text rewrites its rows
  in `page_link`.
- A rename finds the linking pages by index and fixes each with a new version, also set as the working text.
- `GET /v1/pages/{id}/mentions` lists the pages that link to this one, each with the line holding the link.
- Moving a subtree to another base turns into plain text the links the move would break, on both sides, each
  changed page cut as a version first.

## Rules

- No page is created from a PDF's content. A page may link to a PDF; a PDF under a page is a file, never part of its
  text (skill `pdf-files`).
