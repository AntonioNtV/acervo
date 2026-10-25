---
name: ui-design
description: Acervo's visual system (the autoflow "Suíço" look with Segura's ink) - where the design system page is, the rules, tokens, the chat's AI color, screen patterns and the review checklist. Use before designing or changing any screen in web/.
---

# UI design

The design system is the page https://claude.ai/artifact/XZDGhcSkGB6SqhFBBveeyt ("Acervo Design System"): tokens,
typography, spacing, radii, sizes, icons, layouts, every component and the 17 blocks of the editor, each with its
props, variants, measurements and code, documented exactly as the app ships them. Check a token, a type style or a
component there before building or changing one; the tables below summarize it. When the app changes, update the page. The chat
and its AI elements are not in it: for those, the boards and rule 4 below still apply.

The boards are on the canvas https://claude.ai/artifact/Jjq3r6SPUZ9E4jUG7WtqGR ("Acervo · Interface"). Page
"Notion · proposta" sets the look from phase A on: NPagina (shell, page and its blocks, "/" menu), NPasta (folder),
NHistorico (history panel), NPdf (file), NChat (chat panel), NBusca (⌘K) and NMenu (page menu); NBusca, NMenu and
the cover, icon and favorites on NPagina are phase B, and their places stay empty until then. Page "F1 · atual" keeps
the F1 boards (Bases, Base aberta, Soltar PDF, PDF aberto, Caixa de propostas, Página .md, Estados do chat): the chat
states and the proposal still come from there. The look comes from autoflow's "v2 · Suíço"
(https://claude.ai/artifact/6SKxSE3eQAZoNmfh2XBhQ8). Where a board and the code disagree on behavior, the code wins;
the board sets the look.

## The rules

1. Type before boxes: hierarchy from size and gray. No card inside a card, no tinted icon tiles, no button shadow.
2. Color is state: a 6 px dot or the text of an error, never a filled pill.
3. One ink, Segura's green (`--ink` #002311): primary button, switch, focus, citation and data references.
4. **Violet is AI only**: the chat's mark, the "Acervo" label on its messages, the dots of its navigation steps,
   and "proposta do chat" in histories. Nothing else is violet.
5. Navigation recedes: text only, unselected in `--text-3`.
6. Dense but breathing: 13 px body, rows of 44 to 64 px, thin separators.
7. Sizes 11/12/13/15/20/24/32, weights 400 and 500. Index pages get a 32 px title with the count in `--ghost`. The
   text of a page is the exception: 16 px body, headings 24/19/16 (see the shell below).
8. System font and its mono. Files always show their extension in `--text-3` (`Emissão de apólice.md`,
   `Condições Gerais 2026.pdf`): the person always sees what is a page and what is a PDF.
9. Tokens only, so light and dark both work.
10. The only tinted backgrounds besides the focus ring: diff lines (`--add`, `--del`).

## Tokens

| Token | Light | Dark |
|---|---|---|
| `--bg` / `--side` / `--subtle` / `--muted` | #FFFFFF / #FAFAF9 / #F5F5F4 / #EDEDEB | #0B0B0C / #0E0E0F / #151516 / #1D1D1F |
| `--line` / `--line-2` | #EDEDEB / #DEDEDB | #1C1C1E / #2B2B2E |
| `--text` / `--text-2` / `--text-3` / `--ghost` | #0A0A0A / #5C5C58 / #72726D / #959590 | #EDEDEC / #A1A19D / #8A8A85 / #66665F |
| `--ink` / `--on-ink` / `--accent-soft` | #002311 / #FFFFFF / rgba(0,35,17,.08) | #EDEDEC / #0B0B0C / rgba(169,199,181,.13) |
| `--ok` / `--err` / `--warn` / `--run` | #18A058 / #E5484D / #B06F0A / #0A7CFF | #3DD68C / #FF6369 / #F1A10D / #4C9AFF |
| `--ai` / `--ai-text` | #6941C6 / #5B34B5 | #B39DFA / #C8B8FF |
| `--add` / `--del` | rgba(24,160,88,.10) / rgba(229,72,77,.08) | rgba(61,214,140,.12) / rgba(255,99,105,.12) |
| `--desk` (under a PDF page) | #EDEDEB | #151516 |
| `--cover-sage` / `sand` / `stone` / `sky` / `clay` | #E4ECE7 / #EFE9DF / #E9E9E6 / #E3EAF0 / #F0E5E3 | #18221D / #221F19 / #1A1A1B / #161D24 / #241A19 |
| `--cover-moss` / `dawn` / `dusk` | gradients at 135° (`web/src/styles/tokens.css`) | their dark gradients |

`--ai` is an approximation of Segura's lilac; replace it with the brand value when known.

## Screen patterns

| Screen | Layout |
|---|---|
| shell | sidebar 248 px · the screen of the route under a top bar · chat panel 360–400 px at the right when open |
| page | one column, max 720 px, centered; the title is the first line; children of the page as links at its end |
| folder | one column, max 720 px: header (icon, title, description), the list in 36 px rows with what each item holds at the right, drop zone |
| PDF | the file's top bar (pager, zoom, Baixar, ⋯) · the original page on a gray desk |
| history | panel at the right of the page, versions by day; the selected version shows its diff in the page |
| proposal | inside the chat: title, path in mono, diff or folder choice, then Aceitar (ink) · Editar · Rejeitar · Outro lugar |

The shell (NPagina):

- **Sidebar** on `--side` with a right `--line`: "acervo" and the collapse button (remembered), "Bases" and
  "Buscar ⌘K", "Favoritos", then one section per base: its emoji and name as a 12 px `--text-3` label with ⋯ and "+",
  and its tree in 28 px rows indented 14 px per level, a caret on what has children, files with their extension.
  "Nova base" and "Lixeira" sit at the bottom with the language and theme switches.
- **Top bar**, 44 px: the breadcrumb (each part a link), the screen's status in 12 px `--text-3` ("Salvando…",
  "Salvo"), its actions (history), "Chat" in `--ai-text` (it opens the AI) and the ⋯ menu last.
- **Chat panel**: closed by default, toggled by "Chat" and ⌘J; disabled until F2.
- **Blocks** (`web/src/editor/editor.css`): body 16/26 px; H1 24, H2 19, H3 16, weight 500; lists indented 24 px;
  to-do checked in `--text-3` struck through; quote with a 2 px `--line-2` rule; callout on `--subtle`, radius 6, 15
  px; toggle with a caret; code 13 px mono; table with `--line-2` borders and its header on `--side`; page link
  underlined by `--line-2`; Markdown the editor cannot show in a raw block, mono 12 px `--text-3` in a dashed
  `--line-2` border. The handle ("+" and the grip) sits left of the block in `--ghost`; the "/" menu is a 320 px
  popover.

States the chat must cover (board "Estados do chat"): reading a PDF, not sure where (3 options), conflict, already
written, new version of a PDF, not found.

## Checklist before a PR

- Both themes checked; no hex outside the tokens file.
- Every proposal shows where it goes (path in mono) before the person accepts.
- Every answer shows its citations; every "not found" shows where it looked.
- Violet only on AI elements; green only on the ink roles.
- Keyboard: the proposal's buttons are reachable by Tab; Enter accepts only when focus is on Aceitar.
