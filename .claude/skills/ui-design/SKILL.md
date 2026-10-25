---
name: ui-design
description: Acervo's visual system (the autoflow "Suíço" look with Segura's ink) - where the design system page is, the rules, tokens, the chat's AI color, screen patterns and the review checklist. Use before designing or changing any screen in web/.
---

# UI design

The design system is the page https://claude.ai/artifact/XZDGhcSkGB6SqhFBBveeyt ("Acervo Design System"): tokens,
typography, spacing, radii, sizes, icons and every component with its props, variants, measurements and code. Check a
token, a type style or a component there before building or changing one; the tables below summarize it. The chat
and its AI elements are not in it: for those, the boards and rule 4 below still apply.

The boards are on the canvas https://claude.ai/artifact/Jjq3r6SPUZ9E4jUG7WtqGR ("Acervo · Interface"). Page
"Notion · proposta" sets the look from phase A on: NPagina (shell, page and its blocks, "/" menu), NPasta (folder),
NHistorico (history panel), NPdf (file), NChat (chat panel), NBusca (⌘K) and NMenu (page menu); NBusca, NMenu and
the cover, icon and favorites on NPagina are phase B, and their places stay empty until then. Page "F1 · atual" keeps
the F1 boards (Bases, Base aberta, Soltar PDF, PDF aberto, Caixa de propostas, Página .md, Estados do chat): the chat
states and the proposal still come from there. Page "Blocos" holds the page's blocks: Blocos de hoje (what the "/"
menu inserts now), Blocos a adicionar (the 47 planned, by group) and one board per group drawing each new block in
all its states (BlocosTexto, BlocosMidia, BlocosDados, BlocosControles). The look comes from autoflow's "v2 · Suíço"
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
10. The only tinted backgrounds besides the focus ring: diff lines (`--add`, `--del`), the cited passage on a
    PDF page and the person's own highlight in a page (`--mark`).

## Tokens

| Token | Light | Dark |
|---|---|---|
| `--bg` / `--side` / `--subtle` / `--muted` | #FFFFFF / #FAFAF9 / #F5F5F4 / #EDEDEB | #0B0B0C / #0E0E0F / #151516 / #1D1D1F |
| `--line` / `--line-2` | #EDEDEB / #DEDEDB | #1C1C1E / #2B2B2E |
| `--text` / `--text-2` / `--text-3` / `--ghost` | #0A0A0A / #5C5C58 / #72726D / #959590 | #EDEDEC / #A1A19D / #8A8A85 / #66665F |
| `--ink` / `--accent-soft` | #002311 / rgba(0,35,17,.08) | #EDEDEC / rgba(169,199,181,.13) |
| `--ok` / `--err` / `--warn` / `--run` | #18A058 / #E5484D / #B06F0A / #0A7CFF | #3DD68C / #FF6369 / #F1A10D / #4C9AFF |
| `--ai` / `--ai-text` | #6941C6 / #5B34B5 | #B39DFA / #C8B8FF |
| `--add` / `--del` | rgba(24,160,88,.10) / rgba(229,72,77,.08) | rgba(61,214,140,.12) / rgba(255,99,105,.12) |
| `--mark` (highlight) | rgba(176,111,10,.16) | rgba(241,161,13,.20) |
| `--err-text` (small error text, 4.5:1) | #C9302C | #FF6369 |
| `--page` / `--cite` (a PDF page, its cited passage) | #FFFFFF / rgba(0,35,17,.10) | #1A1A1C / rgba(169,199,181,.18) |
| `--tc-gray` / `brown` / `orange` / `yellow` | #72726D / #8A5A3C / #C2570C / #A16207 | #A1A19D / #C49A7C / #F2994A / #E2B93B |
| `--tc-green` / `blue` / `pink` / `red` | #18794E / #0B6BCB / #C2185B / #D92D20 | #3DD68C / #5EB0EF / #F17EB8 / #FF6369 |

The `--tc-*` set is the text color the person picks in a page; it has no violet, which stays AI only.

`--ai` is an approximation of Segura's lilac; replace it with the brand value when known.

## Screen patterns

| Screen | Layout |
|---|---|
| shell | sidebar 248 px · the screen of the route under a top bar · chat panel 360–400 px at the right when open |
| page | one column, max 720 px, centered; the title is the first line; children of the page as links at its end |
| folder | header (icon, title, description), filters Tudo · Páginas · Arquivos, the list with edited and inside columns, drop zone |
| PDF | the file's top bar (pager, zoom, Baixar, ⋯) · the original page on a gray desk |
| history | panel at the right of the page, versions by day; the selected version shows its diff in the page |
| proposal | inside the chat: title, path in mono, diff or folder choice, then Aceitar (ink) · Editar · Rejeitar · Outro lugar |

The shell (NPagina):

- **Sidebar** on `--side` with a right `--line`: "acervo" and the collapse button (remembered), "Buscar ⌘K" and
  "Recentes" (inert until phase B), then one section per base: its name as a 12 px `--text-3` label with ⋯ and "+",
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

### Planned blocks (page "Blocos")

Every block is drawn in all its states: just inserted (empty), editing (its source or popover), read, hover or
selected (`--accent-soft`), uploading and error (`--err` text that says what to do). Popovers sit on `--bg`, radius 8, a 1 px `--line-2` border and no shadow,
30 px items.

- **Text and structure.** H4 15/500, H5 13/500, H6 13/500 in `--text-2`. A collapsible heading is a heading with the
  toggle's 18 px caret gutter; collapsed, it shows "3 blocos" in `--ghost`. The table of contents is links in
  `--text-2`, 14/22, indented 16 px per level, no box, the current section in `--text`. Equations are centered, with
  no background, in a serif math face; inline ones use the same face. A Mermaid diagram has `--text` strokes, `--line-2`
  edges, nodes on `--bg`, a 1 px `--line` frame of radius 7 like code, and an Editar/Ver switch; one that fails shows
  its source as a raw block. A footnote is a superscript number in `--text-3`, with the notes at the page's end under a
  `--line` rule, 13 px `--text-2`. A button block is a secondary button, never ink. Emoji are inline text only. A date
  is text with a 14 px calendar icon, underlined by `--line-2` like a page link; an overdue reminder is `--err` text,
  never a pill. Highlight is `--mark`; text color comes only from `--tc-*`.
- **Media and links.** An image takes the column (max 720 px), radius 6, no border, with its caption 13 px `--text-3`
  below it. File, audio and video are a 44 px row: the icon, the name with its extension in `--text-3`, the size in
  tabular nums and a quiet Baixar. Video plays in a 16:9 box on `--subtle`; audio is a slim row player. The link
  preview is the one framed block: 1 px `--line`, radius 7, title 14/500, two lines of description, the domain in mono,
  an image area on the right. An embed has the same frame, the provider's ratio, and the domain plus "Abrir no site"
  under it. A PDF page is the original page on the gray desk, with `Arquivo.pdf · p. 12` under it; it opens the PDF at
  that page and never copies it. A synced block sits flush with the page; on hover it gets a `--line-2` frame and a
  line saying where it comes from ("de Renovação.md › Documentos"), plus "Editar na origem". "Pedir à IA" is violet
  (it is the AI): it writes a **proposal** inline (diff on `--add`, Aceitar ink · Editar · Rejeitar), never the page
  itself. A mention of a person is the name at weight 500, with no pill.
- **Databases and views.** A database breaks out of the 720 px column up to 1040 px. Every view shares one header:
  the title 15/500, the views as text tabs (rule 5), quiet Filtrar · Ordenar · Buscar and a secondary "Nova". The
  table keeps the page's table style. Status is always a 6 px dot and its text. Money is tabular and right aligned. A
  board has columns by status with the count in `--text-3`, and cards with a 1 px `--line` at radius 6, no shadow. A
  calendar has `--line` grid lines and today's number in an ink circle. A timeline has `--muted` bars with today's line
  in ink. A chart puts one series in ink; status colors only when a series means a status. A form uses real labels
  and an ink Enviar. A map is drawn with `--subtle` land and ink pins. A linked view says where it comes from in 12 px
  `--text-3`.
- **Layout, formulas and controls.** Columns: 2 to 5 with a 32 px gap, a `--line-2` guide to resize them on hover,
  stacked under 640 px. Controls are native inputs on the tokens: `accent-color: var(--ink)`, 30 px, 1 px `--line-2`,
  radius 7. A switch is ink when on; a slider has its filled part and thumb in ink; a rating uses stroke stars filled in
  ink. A formula's result is inline weight 500 with a dotted `--line-2` underline, and hovering it shows the formula
  in mono. An integration says where its data comes from and when it was updated, with a quiet Atualizar. The
  breadcrumb block matches the top bar's. Meeting notes are AI (violet): recording shows a 6 px `--err` dot and a mono
  timer, and the summary arrives as a proposal.

States the chat must cover (board "Estados do chat"): reading a PDF, not sure where (3 options), conflict, already
written, new version of a PDF, not found.

## Checklist before a PR

- Both themes checked; no hex outside the tokens file.
- Every proposal shows where it goes (path in mono) before the person accepts.
- Every answer shows its citations; every "not found" shows where it looked.
- Violet only on AI elements; green only on the ink roles.
- Keyboard: the proposal's buttons are reachable by Tab; Enter accepts only when focus is on Aceitar.
