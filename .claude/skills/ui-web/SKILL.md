---
name: ui-web
description: The React app in web/ - its layout by screen, the generated API client and data hooks, the API key, errors by code, the Markdown editor, the PDF viewer, the chat and its websocket events, i18n, and how to typecheck, lint, test and build it. Use when touching web/.
---

# Web

`web/` is a pnpm project: React 18, TypeScript strict, Vite, Tailwind v4, Radix primitives, TanStack Query. It
talks only to the Acervo API (skill `http-api`). The look is skill `ui-design`.

| Folder in `web/src` | Holds |
|---|---|
| `app/` | router, providers (query client, theme, i18n; the websocket from F2), the frames around the screens, `errors.ts` (text by error code) |
| `api/` | `schema.gen.ts` (generated from `docs/openapi.json`, never edited), `client.ts` (openapi-fetch on the same origin, the types and `apiHeaders` with `X-API-Key`), `testing.tsx` (the one test fake) |
| `data/` | React Query hooks per resource: `kbs.ts`, `tree.ts`, `pages.ts`, `files.ts`, `upload.ts`, on the shared `request.ts` |
| `screens/` | one folder per screen: `bases`, `base` (the tree, drag to move or reorder: the person's own action moves directly), `page` (Ler · Editar · Dividir, history), `file`; from F2 `chat` and `proposals` |
| `viewer/` | the PDF viewer on pdfjs-dist, password prompt |
| `ui/` | primitives on Radix: Button, Dialog, Menu, TextTabs, Dot (status), Input, FileName |
| `i18n/` | one file per screen (`app`, `bases`, `base`, `page`, `file`, `errors`), `ptBR` first and `en` with the same keys |
| `styles/` | `tokens.css` (the table in `ui-design`), `base.css` |

## The key and errors

- The client sends `X-API-Key` from `VITE_API_KEY` in `web/.env.local` (copy `web/.env.local.example`; the same
  value as `API_KEY` in `.env`). pdf.js reads the raw file with the header (`httpHeaders`); images and "Baixar" use
  a signed link from `POST /v1/files/{id}/link` (60 s, path and query only, so it goes through the proxy), so the
  browser streams the file itself. The key never goes in a URL.
- Errors are shown through `app/errors.ts` from `error.error`, the code (`title_taken`, `duplicate` with
  `details.path`, `stale_page`, `same_file`, `not_found`, `unauthorized`), in both locales; a generic text by status
  otherwise. Never the raw `message`.

## Pieces with a chosen library

| Need | Library | Notes |
|---|---|---|
| Markdown source | CodeMirror 6 | the editor of Editar and Dividir |
| Markdown preview | react-markdown + remark-gfm | wiki links `[[…]]` resolved by a small remark plugin |
| PDF viewer | pdfjs-dist | renders the **original file** from `/v1/files/{id}/raw`; a citation opens it at its page and highlights the passage |
| diffs | rendered from the proposal's `Patch`, not computed in the browser | |

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
