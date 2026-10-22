---
name: web-app
description: The React app in web/ - its layout by feature, the generated API client, the Markdown editor, the PDF viewer, the chat and its websocket events, i18n, and how to typecheck, test and build it. Use when touching web/.
---

# Web app

`web/` is a pnpm project: React 18, TypeScript, Vite, Tailwind v4, Radix primitives, TanStack Query. The look is
skill `ui-design`; the routes and types come from skill `http-contract`.

| Folder in `web/src` | Holds |
|---|---|
| `app/` | router, providers (query client, websocket, theme, i18n) |
| `features/bases/` | the Bases screen |
| `features/tree/` | the tree of a base, drag to move (which creates a `move` proposal) |
| `features/page/` | page reading, editing (Ler · Editar · Dividir) and history |
| `features/pdf/` | the PDF viewer and the section map |
| `features/chat/` | the chat: Capturar and Perguntar, messages, proposal blocks, navigation steps, citations |
| `features/proposals/` | the Propostas screen and its detail drawer |
| `ui/` | primitives on Radix: Button, Dialog, Menu, TextTabs, Dot (status), Input |
| `api/` | `schema.gen.ts` (generated, never edited), `client.ts` (openapi-fetch), `queries.ts`, `events.ts` |
| `i18n/` | one file per feature, `ptBR` first and `en` |
| `styles/` | `tokens.css` (the table in `ui-design`), `base.css` |

## Pieces with a chosen library

| Need | Library | Notes |
|---|---|---|
| Markdown source | CodeMirror 6 | the editor of Editar and Dividir |
| Markdown preview | react-markdown + remark-gfm | wiki links `[[…]]` resolved by a small remark plugin |
| PDF viewer | pdfjs-dist | renders the **original file** from `/files/{id}/raw`; a citation opens it at its page and highlights the passage |
| diffs | rendered from the proposal's `Patch`, not computed in the browser | |

The app never shows a PDF as Markdown and never offers "convert".

## Chat

- Messages stream over the websocket (`answer.delta`); navigation steps arrive as `nav.step` and render as the
  collapsible list with probabilities.
- A proposal block reads its state from the `proposal.updated` event, so accepting from Propostas updates the chat.
- Dropping a PDF anywhere in a base uploads it and opens the chat on the intake card.

## Rules

- Texts go through `t("<feature>.<key>")`, with the key in both locales.
- Colors and spacing only from `tokens.css`.
- Server state only through `api/queries.ts`; no `fetch` with a path string.

## Commands

```bash
cd web
pnpm install
pnpm gen:api        # after an API change
pnpm typecheck
pnpm test           # vitest + Testing Library, tests next to the code, in pt-BR
pnpm build
```
