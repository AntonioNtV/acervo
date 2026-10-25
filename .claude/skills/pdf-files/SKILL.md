---
name: pdf-files
description: Everything Acervo does with a PDF or any uploaded file - storage by content, the allowed operations, versions, duplicates, the raw bytes and signed links, and reading a PDF's metadata. Use for any code that touches a file.
---

# PDF files

A PDF, like any other uploaded file, is a node of kind `file` (title with its extension) with a row in `file`;
older files of the node live in `file_version`. Generic files follow every rule here; only the page count and the
password flag are PDF-specific. `FileService` owns what happens to a file; the pipeline only reads it.

**A PDF stays a PDF.** It is stored byte for byte as uploaded and shown as the original file. It is never converted
to Markdown, never becomes a page, and its text is never stored as content of the base.

| Piece | File | What it is |
|---|---|---|
| storage | `services/storage.py` | S3/MinIO; key `kb/<kb_id>/<sha256>`, by content and immutable: move and rename touch only the database |
| file use cases | `services/file_service.py` | save, replace with history, restore, duplicates, open the raw bytes, signed links |
| reader | `pipeline/pdf/reader.py` | PyMuPDF: page count and password flag |

## Allowed operations

Save (into a folder, a page or the base's root), move, rename, replace (with history), restore an older content,
trash and restore, download. Page count and the `protected` flag (a password-protected PDF) are metadata, not
content. A rename keeps the extension. Duplicating a page never copies the files under it. Any other operation on
a PDF is a bug.

## Duplicates and versions

Same `sha256` as a file already in the base, in the trash or in any file's history → `duplicate` ("já está em
<caminho>", with `details.path`, `trashed` and `history`), nothing stored; replacing refuses the same way. Uploads stream to storage with no size limit, so a duplicate is only known once the
bytes arrived; they are then dropped. Replacing a file with its own bytes, or restoring the content it already has → `same_file`. Replacing moves the
current content to `file_version`; restoring one brings it back the same way, so nothing is lost.

## Reading the bytes

`GET /v1/files/{id}/raw` serves the original bytes (one `Range` honored) under the original file name, with the
`X-API-Key` header or a signed link from `POST /v1/files/{id}/link` (60 s, skill `http-api`). The web app renders
the original file with pdf.js (skill `ui-web`); nothing is extracted or cached from it.
