---
name: ui-design
description: Acervo's visual system - a quiet, type-led look with one green ink - its rules, tokens, screen patterns and the review checklist. Use before designing or changing any screen in web/.
---

# UI design

The look is quiet and led by type: white space, gray text in a few steps, thin lines and one dark green ink. The code
is the reference: `web/src/styles/tokens.css` for the values, the screens in `web/src/screens/` for the patterns.

## The rules

1. Type before boxes: hierarchy from size and gray. No card inside a card, no tinted icon tiles, no button shadow.
2. Color is state: a 6 px dot or the text of an error, never a filled pill.
3. One ink, dark green (`--ink` #002311): primary button, switch, focus ring and selection.
4. Navigation recedes: text only, unselected in `--text-3`.
5. Dense but breathing: 13 px body, thin separators, tree rows of 26 px.
6. Sizes 11/12/13/15/20/24/32, weights 400 and 500. Index pages get a 32 px title with the count in `--ghost`. The
   text of a page is the exception: 16 px body, headings 24/19/16 (see the blocks below).
7. System font and its mono. Files always show their extension in `--text-3` (`Emissão de apólice.md`,
   `Condições Gerais 2026.pdf`): the person always sees what is a page and what is a PDF.
8. Tokens only, so light and dark both work.
9. The only tinted backgrounds besides the focus ring and covers: diff lines (`--add`, `--del`) and the desk under a
   PDF (`--desk`).

## Tokens

| Token | Light | Dark |
|---|---|---|
| `--bg` / `--side` / `--subtle` / `--muted` | #FFFFFF / #FAFAF9 / #F5F5F4 / #EDEDEB | #0B0B0C / #0E0E0F / #151516 / #1D1D1F |
| `--line` / `--line-2` | #EDEDEB / #DEDEDB | #1C1C1E / #2B2B2E |
| `--text` / `--text-2` / `--text-3` / `--ghost` | #0A0A0A / #5C5C58 / #72726D / #959590 | #EDEDEC / #A1A19D / #8A8A85 / #66665F |
| `--ink` / `--on-ink` / `--accent-soft` | #002311 / #FFFFFF / rgba(0,35,17,.08) | #EDEDEC / #0B0B0C / rgba(169,199,181,.13) |
| `--ok` / `--err` / `--warn` / `--run` | #18A058 / #E5484D / #B06F0A / #0A7CFF | #3DD68C / #FF6369 / #F1A10D / #4C9AFF |
| `--add` / `--del` | rgba(24,160,88,.10) / rgba(229,72,77,.08) | rgba(61,214,140,.12) / rgba(255,99,105,.12) |
| `--desk` | #EDEDEB | #151516 |
| `--cover-*` | the cover gallery (`gallery:<slug>`): sage, sand, stone, sky, clay, and the gradients moss, dawn, dusk; soft in both themes so the buttons over a cover read | |

## Screen patterns

| Screen | Layout |
|---|---|
| shell | sidebar 248 px · the screen of the route under a 44 px top bar |
| bases (`/bases`) | the bases as cards in a grid (min 280 px), at most 1040 px wide |
| page | one column, max 720 px, centered; optional cover (200 px) and icon above the title; the title is the first line; children of the page as links at its end, then the pages that mention it |
| folder | same column: cover, icon, title, description (editable), the list of children, "Nova página" and "Enviar arquivos"; the whole column is a drop zone |
| file | the top bar (pager, zoom, Baixar, ⋯ with Substituir and Versões) · the info line · the original page on the `--desk` |
| history | panel 320 px at the right of the page, versions by day; the selected version shows its diff in the page |
| search (⌘K) | a palette over the screen: recent pages of the base, then title results with their path, and "Criar página" |
| trash (`/lixeira`) | trashed bases and each base's trashed items, with where they were |

The shell:

- **Sidebar** on `--side` with a right `--line`: the brand and the collapse button (remembered), "Bases" and
  "Buscar ⌘K", the favorites, then one section per base: its name as a 12 px `--text-3` label with ⋯ and "+", and
  its tree in 26 px rows indented 14 px per level, a caret on what has children, files with their extension.
  "Nova base" and "Lixeira" sit at the bottom with the language and theme switches.
- **Top bar**, 44 px: the breadcrumb (each part a link), the screen's status in 12 px `--text-3` ("Salvando…",
  "Salvo"), its actions (history) and the ⋯ menu last.
- **Blocks** (`web/src/editor/editor.css`): body 16 px; H1 24, H2 19, H3 16, weight 500; lists indented 24 px;
  to-do checked in `--text-3` struck through; quote with a 2 px `--line-2` rule; callout on `--subtle`, radius 6, 15
  px; toggle with a caret; code 13 px mono; table with `--line-2` borders and its header on `--side`; page link
  underlined by `--line-2`; Markdown the editor cannot show in a raw block, mono 12 px `--text-3` in a dashed
  `--line-2` border. The handle ("+" and the grip) sits left of the block in `--ghost`; the "/" menu is a 320 px
  popover.

## Checklist before a PR

- Both themes checked; no hex outside the tokens file.
- Files show their extension; a PDF is shown as the original file, never as text.
- Every action that moves or trashes says where it goes or where it came from.
- Green only on the ink roles.
- Keyboard: menus, dialogs and the palette work by Tab, arrows, Enter and Esc.
