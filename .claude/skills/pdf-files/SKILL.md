---
name: pdf-files
description: Everything Acervo does with a PDF - storage, the allowed operations, versions, the section map (bookmarks, then table of contents, then generated) and reading pages as text or image. Use for any code that touches a PDF.
---

# PDF files

A PDF, like any other uploaded file, is a node of kind `file` (title with its extension) with a row in `file`;
older files of the node live in `file_version`. Generic files follow every rule here; only the map and reading
pages are PDF-specific. `FileService` owns what happens to a file; the pipeline only reads it.

**A PDF stays a PDF.** It is stored byte for byte as uploaded and shown as the original file. It is never converted
to Markdown, never becomes a page, never edited, and its text is never stored as content of the base: its index
keeps extracted text for search only.

| Piece | File | What it is |
|---|---|---|
| storage | `services/storage.py` | S3/MinIO; key `kb/<kb_id>/<sha256>`, by content and immutable: move and rename touch only the database |
| file use cases | `services/file_service.py` | save, replace with history, restore, duplicates, open the raw bytes |
| reader | `pipeline/pdf/reader.py` | PyMuPDF: page count and password flag today; bookmarks, page text and page image from F3 |
| map | `pipeline/pdf/map.py`, `domain/pdf_map.py` | builds the section map; `FileService` stores it |
| intake job | `worker/pdf_intake.py` | upload → card → Curator → proposal (F2) |

## Allowed operations

Save, move, rename, replace (with history), trash and restore. Page count and the `protected` flag (a
password-protected PDF) are metadata, not content. The person does these directly; an agent only proposes them.

| Operation | Proposal kind (agents) | Notes |
|---|---|---|
| save | `save_pdf` | to a folder, never to a page |
| move | `move` | to another folder |
| rename | `rename` | the name keeps its extension |
| replace | `replace_pdf` | the old file stays in the history and can be restored |
| trash, restore | none from agents | only the person, from the UI |

Any other operation on a PDF is a bug. `services/proposal_service.py` refuses a proposal that would write a PDF's content
anywhere else.

## The section map

The map is an index, not content: a tree of `{title, pages: [first, last], children}`. Built after the PDF is saved,
in this order, recording `map_origin`:

1. `bookmarks`: the PDF's own outline, when it has one.
2. `toc`: the table of contents page, located in the first pages and read by the LLM.
3. `generated`: only when neither exists, the LLM `pdf_map` role groups the titles detected per page.

The map is what lets the Navigator go to pages 14–15 of a 180-page file without reading the rest.

## The index

Every PDF (and every page, skill `markdown-pages`) gets a structural index, `DocIndex` in `domain/index.py`, stored
in `node_index` (one row per node, `repositories/node_index.py`, `uow.indexes`). It is built in the background, one
job at a time per node, when the PDF is uploaded or replaced; nothing in it calls an LLM and no summary is stored.

- **Sections**: from the PDF's bookmarks, else from headings detected by font size, else one section per page. A
  section keeps its page range and continues across pages.
- **Blocks**: paragraph, heading, table, figure, list, each with its page, its box in PDF points and the page's
  size, so a citation opens the page with that block highlighted.
- **Passages**: what Jev scores, inside one section, at most `RetrievalLimits.passage_chars` with
  `passage_overlap` repeated; a passage never splits a table row and repeats the table's header.
- **Outline** (the titles, for folder descriptions and the menu) and **stats** (pages, words, tables, figures), so
  "how many" is answered from counts, never from samples.
- A PDF with a password or no text is indexed by its name and outline only; `note` says so.

An index belongs to one version (`version_key`, the file's sha256). A new version is built under `building_key`
while the previous index stays readable; `finish` swaps it in only if no later build superseded it. The row's
status (`building`, `ready`, `failed`) is the tree's `index_state`.

## Reading pages

- Text: the PDF's text layer, page by page, read when a question needs it. Not cached as content of the base.
- Image: the page rendered at 144 dpi for the vision role, when the page has a table, a form or no text layer.
- Scanned PDFs (no text layer) are out of the MVP: they are saved, the map is generated from page images, and the
  UI says reading is limited.

## Duplicates and versions

Same `sha256` as a file already in the base, trash included → "já está em <caminho>", nothing stored and no
proposal. Uploads stream to storage with no size limit, so a duplicate is only known once the bytes arrived; they
are then dropped. Different hash but Jev says it is a
new version of a file in the chosen folder → `replace_pdf`.
