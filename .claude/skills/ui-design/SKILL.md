---
name: ui-design
description: Acervo's visual system (the autoflow "Suíço" look with Segura's ink) - the rules, tokens, the chat's AI color, screen patterns and the review checklist. Use before designing or changing any screen in web/.
---

# UI design

The boards are on the canvas https://claude.ai/artifact/Jjq3r6SPUZ9E4jUG7WtqGR ("Acervo · Interface"): Bases, Base
aberta, Soltar PDF, PDF aberto, Caixa de propostas, Página .md and Estados do chat. The look comes from autoflow's
"v2 · Suíço" (https://claude.ai/artifact/6SKxSE3eQAZoNmfh2XBhQ8). Where a board and the code disagree on behavior,
the code wins; the board sets the look.

## The rules

1. Type before boxes: hierarchy from size and gray. No card inside a card, no tinted icon tiles, no button shadow.
2. Color is state: a 6 px dot or the text of an error, never a filled pill.
3. One ink, Segura's green (`--ink` #002311): primary button, switch, focus, citation and data references.
4. **Violet is AI only**: the chat's mark, the "Acervo" label on its messages, the dots of its navigation steps,
   and "proposta do chat" in histories. Nothing else is violet.
5. Navigation recedes: text only, unselected in `--text-3`.
6. Dense but breathing: 13 px body, rows of 44 to 64 px, thin separators.
7. Sizes 11/12/13/15/20/24/32, weights 400 and 500. Index pages get a 32 px title with the count in `--ghost`.
8. System font and its mono. Files always show their extension in `--text-3` (`Emissão de apólice.md`,
   `Condições Gerais 2026.pdf`): the person always sees what is a page and what is a PDF.
9. Tokens only, so light and dark both work.
10. The only tinted backgrounds besides the focus ring: diff lines (`--add`, `--del`) and the cited passage on a
    PDF page.

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

`--ai` is an approximation of Segura's lilac; replace it with the brand value when known.

## Screen patterns

| Screen | Layout |
|---|---|
| index (Bases, Propostas) | side nav 220–240 px, content max 1040 px, 72 px top padding, 32 px title |
| inside a base | tree 248 px · content (max 720 px for a page) · chat 360–400 px |
| PDF | tree · section map 210–230 px · the original page on a gray desk · chat |
| proposal | inside the chat: title, path in mono, diff or folder choice, then Aceitar (ink) · Editar · Rejeitar · Outro lugar |

States the chat must cover (board "Estados do chat"): reading a PDF, not sure where (3 options), conflict, already
written, new version of a PDF, not found.

## Checklist before a PR

- Both themes checked; no hex outside the tokens file.
- Every proposal shows where it goes (path in mono) before the person accepts.
- Every answer shows its citations; every "not found" shows where it looked.
- Violet only on AI elements; green only on the ink roles.
- Keyboard: the proposal's buttons are reachable by Tab; Enter accepts only when focus is on Aceitar.
