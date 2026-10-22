---
name: pdf-files
description: Everything Acervo does with a PDF - storage, the allowed operations, versions, the section map (bookmarks, then table of contents, then generated) and reading pages as text or image. Use for any code that touches a PDF.
---

# PDF files

**A PDF stays a PDF.** It is stored byte for byte as uploaded and shown as the original file. It is never converted
to Markdown, never becomes a page, and its text is never stored as content of the base.

| Piece | File | What it is |
|---|---|---|
| storage | `pdfs/storage.py` | S3/MinIO; the key mirrors the folder path; content hash `sha256` |
| reader | `pdfs/reader.py` | PyMuPDF: metadata, bookmarks, page text, page image |
| map | `pdfs/map.py` | builds and stores the section map |
| versions | `pdfs/versions.py` | replace with a newer file, keep the old one in the file's history |
| intake job | `jobs/pdf_intake.py` | upload → card → Curator → proposal |

## Allowed operations

| Operation | Proposal kind | Notes |
|---|---|---|
| save | `save_pdf` | to a folder, never to a page |
| move | `move` | to another folder |
| rename | `rename` | the name keeps `.pdf` |
| replace | `replace_pdf` | the old file stays in the history and can be restored |
| delete | none from agents | only the person, from the UI |

Any other operation on a PDF is a bug. `proposals/apply.py` refuses a proposal that would write a PDF's content
anywhere else.

## The section map

The map is an index, not content: a tree of `{title, pages: [first, last], children}`. Built after the PDF is saved,
in this order, recording `map_origin`:

1. `bookmarks`: the PDF's own outline, when it has one.
2. `toc`: the table of contents page, located in the first pages and read by the LLM.
3. `generated`: only when neither exists, the LLM `pdf_map` role groups the titles detected per page.

The map is what lets the Navigator go to pages 14–15 of a 180-page file without reading the rest.

## Reading pages

- Text: the PDF's text layer, page by page, read when a question needs it. Not cached as content of the base.
- Image: the page rendered at 144 dpi for the vision role, when the page has a table, a form or no text layer.
- Scanned PDFs (no text layer) are out of the MVP: they are saved, the map is generated from page images, and the
  UI says reading is limited.

## Duplicates and versions

Same `sha256` as a file already in the base → "already in <path>", no proposal. Different hash but Jev says it is a
new version of a file in the chosen folder → `replace_pdf`.
