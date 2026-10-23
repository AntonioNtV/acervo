---
name: ui-web
description: The React app in web/ - its layout by screen, the shell, the generated API client and data hooks, the API key, errors by code, the block editor with autosave and history, the PDF viewer, the chat and its websocket events, i18n, and how to typecheck, lint, test and build it. Use when touching web/.
---

# Web

`web/` is a pnpm project: React 18, TypeScript strict, Vite, Tailwind v4, Radix primitives, TanStack Query. It
talks only to the Acervo API (skill `http-api`). The look is skill `ui-design`.

| Folder in `web/src` | Holds |
|---|---|
| `app/` | router, providers (query client, theme, i18n; the websocket from F2), `ShellFrame` (sidebar · screen · chat panel), `Home` (`/`), `NodeView` (the screen by node kind), `lastPage.ts`, `errors.ts` (text by error code) |
| `api/` | `schema.gen.ts` (generated from `docs/openapi.json`, never edited), `client.ts` (openapi-fetch on the same origin, the types and `apiHeaders` with `X-API-Key`), `testing.tsx` (the one test fake) |
| `data/` | React Query hooks per resource: `kbs.ts`, `tree.ts`, `pages.ts`, `files.ts`, `upload.ts`, on the shared `request.ts` |
| `screens/` | one folder per screen: `shell` (the frame around every screen), `folder`, `page`, `file`; `base` keeps the upload list and node names, `bases` the base dialog and dates; from F2 `chat` and `proposals` |
| `editor/` | `BlockEditor`: the page's blocks on TipTap, read from and written to Markdown (`markdown.ts`, `extensions.ts`) |
| `viewer/` | the PDF viewer on pdfjs-dist, password prompt |
| `ui/` | primitives on Radix: Button, IconButton, Icon, Dialog, Menu, Dot (status), Input, Kbd, FileName |
| `i18n/` | one file per screen (`app`, `shell`, `bases`, `base`, `folder`, `page`, `file`, `editor`, `errors`), `ptBR` first and `en` with the same keys |
| `styles/` | `tokens.css` (the table in `ui-design`), `base.css` |

Routes: `/` (the last page seen, else the first base's first node, else "Nova base"), `/lixeira` (trashed bases and
the trash of each base), `/kbs/:kbId` (a base's root), `/kbs/:kbId/n/:nodeId` (a node, by kind). Every route renders
inside the shell.

## The shell (`screens/shell`)

- `Sidebar`: every base as a `BaseSection` (menu: rename, describe, new folder, Lixeira; "+" for a page at its root)
  with its `TreeRows`: folders and pages open lazily (a caret from `has_children`), inline rename, "Nova página" on a
  folder or a page, files dropped on a row upload into it. Dragging moves a node into a folder or a page, or between
  siblings, inside its own base; the API refuses a move into the node itself or below it. The person's own action
  moves directly, no proposal.
- `TopBar`: every content screen renders its own with the breadcrumb (`kbId`, `nodeId`) and fills its slots:
  `status`, `actions`, `menu`. "Chat" and ⌘J (Ctrl+J) toggle `ChatPanel`, a placeholder until F2.
- `shell.tsx`: `useShell()` (sidebar and chat open) and `useCurrent()` (base and node of the URL).
- Per-browser conveniences in `localStorage`, every access in try/catch and the app working without it: the last page
  (`acervo.lastPage`), the sidebar (`acervo.sidebar`) and the open sections (`acervo.openBases`). Nothing shared or
  that must persist goes there.

## Folder and file screens

- `screens/folder`: NPasta. Title renamed inline, the node description editable, filters Tudo · Páginas · Arquivos
  with counts, the list (name with extension, edited, what it holds), "Nova página", "Enviar arquivos" and a drop
  zone. A page always opens in the page screen, even with no text.
- `screens/file`: NPdf. Pager, zoom, Baixar and ⋯ (Substituir, Versões) on the top bar; the info line (original file,
  pages, size, versions, the folder or page it is in); the desk with the viewer.

## The page screen (`screens/page`)

- No modes: the title is the first line and renames the node (debounced; the API fixes the links to it), then
  `BlockEditor` with the page's Markdown, then the page's children as links. "/subpágina" creates a sub-page under it.
- **Autosave**: about 1 s after typing stops, `PUT /v1/pages/{id}/text` with the `revision` it read; the top bar says
  "Salvando…" then "Salvo". No version per save: the server cuts versions by editing session (skill
  `markdown-pages`).
- **Leaving**: leaving the page or hiding the tab calls `POST /v1/pages/{id}/leave` with `fetch(..., {keepalive:
  true})` and the key header (`sendBeacon` cannot send it), so closing the tab loses nothing.
- **Another tab**: a 409 `stale_page` carries the newest `markdown` and `revision` in `details`; the editor remounts
  with them and a notice says the page changed elsewhere and the refused text was kept as a version.
- **History** (NHistorico): a panel at the right; opening it cuts the working text first. Versions by day with time,
  author and editing span; selecting one shows its text with additions and removals marked in the page (the line diff
  from `GET .../versions/{id}/diff`), with "Restaurar esta versão" and "Voltar à atual". Restoring writes a new
  version; none is lost.

## The block editor (`editor/`)

`BlockEditor` takes `markdown` (initial only: another text comes in by remounting with a new `key`), `onChange`
(the whole page after each edit, never on load), `resolveLink(title)` (`{href}`, `"missing"` or `"ambiguous"`),
`onCreateSubPage(title)` (resolves to the title it got) and `pageTitles` (for the `[[` and `@` picker). "/" opens the
block menu with search; Markdown shortcuts work as typed; each block has a handle (drag, turn into, duplicate,
delete) and "+"; pasted Markdown or rich text keeps its blocks.

| Block | Markdown |
|---|---|
| paragraph, H1–H3, bullets, numbers, quote, code, divider | CommonMark |
| to-do | `- [ ]` / `- [x]` (GFM task list) |
| table | GFM table (no merged cells) |
| callout | GFM alert `> [!NOTE]` (also `TIP`, `IMPORTANT`, `WARNING`, `CAUTION`) |
| toggle | `<details><summary>…</summary>…</details>` |
| page link, sub-page | `[[Title]]` |
| anything else (raw HTML, footnotes, definitions, unknown syntax) | a raw block (or raw inline), kept as written |

The round-trip is the rule: an untouched block is written back byte for byte (only line endings become `\n`), an
edited one in a standard form. A new block kind comes with a fixture in `editor/fixtures/` and its round-trip test in
`markdown.test.ts`.

## The key and errors

- The client sends `X-API-Key` from `VITE_API_KEY` in `web/.env.local` (copy `web/.env.local.example`; the same
  value as `API_KEY` in `.env`). pdf.js reads the raw file with the header (`httpHeaders`); images and "Baixar" use
  a signed link from `POST /v1/files/{id}/link` (60 s, path and query only, so it goes through the proxy), so the
  browser streams the file itself. The key never goes in a URL.
- Errors are shown through `app/errors.ts` from `error.error`, the code (`title_taken`, `duplicate` with
  `details.path`, `stale_page` with the newest `markdown` and `revision`, `same_file`, `not_found`, `unauthorized`),
  in both locales; a generic text by status otherwise. Never the raw `message`.

## Pieces with a chosen library

| Need | Library | Notes |
|---|---|---|
| page editor | TipTap 3.31.4 with `@tiptap/markdown` | pinned; see the block editor above |
| PDF viewer | pdfjs-dist | renders the **original file** from `/v1/files/{id}/raw`; a citation opens it at its page and highlights the passage |
| diffs | rendered from the API (a version's line diff, a proposal's `Patch`), not computed in the browser | |

The app never shows a PDF as Markdown and never offers "convert".

## Chat (F2)

- Messages stream over the websocket (`answer.delta`); navigation steps arrive as `nav.step` and render as the
  collapsible list with probabilities.
- A proposal block reads its state from the `proposal.updated` event, so accepting from Propostas updates the chat.
- Dropping a PDF anywhere in a base uploads it and opens the chat on the intake card.

## Rules

- Texts go through `t("<screen>.<key>")`, with the key in both locales.
- Colors and spacing only from `tokens.css` through Tailwind theme variables; no palette classes.
- Server state only through `data/`; no `fetch` with a path string. A contract change is `make openapi` in the same
  PR.

## Commands

```bash
make web-check      # from the root: install, typecheck, lint, test, build (what CI runs)
cd web
pnpm dev            # http://localhost:5173, proxies /v1 to VITE_API_URL (the API on :8000)
pnpm gen:api        # after an API change; `make openapi` also exports docs/openapi.json first
pnpm typecheck
pnpm lint           # ESLint
pnpm test           # vitest + Testing Library, tests next to the code, in pt-BR
pnpm build
```
