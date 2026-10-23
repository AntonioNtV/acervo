---
name: navigator-agent
description: How Acervo answers questions by search over the structural index, without embeddings - the tree, Jev's menus and beam, evidence scores, the limits, the tools the chat's LLM gets, citations and "not found". Use when changing how questions are answered or how search moves inside a large PDF.
---

# Search

A question is answered by Jev descending the base's tree and scoring the evidence; the LLM only writes the answer.
There are no embeddings, no vector store and nothing retrieved by similarity. If you are about to add one, stop: it
breaks rule 4 of `CLAUDE.md`. Passages exist, but only as evidence units inside a section that Jev scores.

Every file and page has a structural index (`DocIndex` in `domain/index.py`, skill `pdf-files`): sections, blocks
with their positions, passages, an outline and stats. A search returns a `SearchResult`: the `Evidence` kept, the
`SearchStep`s it took and where it looked.

The trigram index on node titles serves the person's name filter in the tree. It matches titles only and no search
uses it.

## The tree

Search sees one tree: folders → pages and PDFs → their sections → passages. Each document also has a statistics
branch (pages, words, tables, figures, how often a term appears), so "how many" is answered from counts, never from
samples. Deleted and trashed nodes never enter it.

What Jev sees of an option is built at search time (skill `markdown-pages`): a folder from its children's titles and
outlines, a document from its outline, a section from its title, page range and up to 3 excerpts chosen for the
question. A description the person wrote comes first.

## The descent

1. **Menus.** At each level Jev gets one `Choice` per open route over its children plus "none"; more than
   `RetrievalLimits.menu` children are grouped. Up to `menus_per_call` menus go in one Jev call.
2. **Beam.** The `beam` best routes stay open; the others are deferred. A route's score ranks paths only and is never
   shown as a confidence.
3. **Evidence.** A section reached gives its passages to Jev as `Score` questions (0–3 usefulness, `per_score_call`
   per call) before going deeper. Passages under `Thresholds.evidence_min` are dropped.
4. **Stop** when one passage reaches `Thresholds.evidence_enough`, or when partial ones together cover the question;
   otherwise widen to deferred routes. After `sections_per_document` sections of one document, other documents get
   priority.
5. **Shortcut.** Documents whose title or headings match the question's terms are proposed as extra routes, still
   routed and scored by Jev.

Every Jev call goes to the decision log with the question asked and the run. An invalid answer from Jev fails the
search visibly ("Não consegui buscar agora · Tentar de novo"); there is no silent fallback.

## Limits (`RetrievalLimits` in `core/settings.py`)

| Field | Default | Limits |
|---|---|---|
| `menu` | 64 | options per menu, besides "none" |
| `menus_per_call` | 4 | menus per Jev call |
| `beam` | 4 | routes kept open per level |
| `expansions` | 96 | nodes and sections opened per search |
| `passages` | 96 | passages scored per search |
| `per_score_call` | 16 | passages per Jev call |
| `results` | 12 | evidence returned |
| `result_chars` | 24000 | characters of evidence returned |
| `sections_per_document` | 8 | sections of one document before others get priority |
| `description_chars` | 1200 | characters of a built description |
| `passage_chars`, `passage_overlap` | 2400, 200 | how the index cuts passages |
| `llm_steps`, `llm_tool_steps` | 6, 5 | steps of the chat's LLM in one reply, and those that call tools |

jevbox's values are the starting point; the retrieval eval recalibrates them (skill `evals`).

## The chat's tools

The chat's LLM chooses when to use them; Jev decides inside them (rule 6).

| Tool | Does |
|---|---|
| `search(question)` | runs the descent on a self-contained question (the LLM rewrites "e no Bradesco?" with the subject) and returns up to `results` cited passages with path, section and page |
| `open(document, outline \| pages)` | a document's outline, or up to 5 pages of text |
| `view(pdf, pages)` | up to 2 PDF page images, for charts and scans |

External agents get the same engine over MCP as `search` and `fetch`. While searching, the reply's activity line
follows the trace (`UiActivityPart`): "Procurando em Bradesco › Auto", "Lendo Tabela auto 2026, p. 4".

## Citations

The answer cites each claim with the smallest block that supports it. A `Citation` carries the node, the PDF page,
the `block_id` and its `highlight` box in PDF points, so the web app opens the PDF at that page with the block
highlighted, or the page scrolled to that paragraph (skill `ui-web`).

Nothing found within the limits: the answer says it is not in the base and where it looked. It never answers a
question about the base from general knowledge.
