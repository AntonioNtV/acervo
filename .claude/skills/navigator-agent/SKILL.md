---
name: navigator-agent
description: The agent that answers questions in Acervo by navigation, without chunks or embeddings - its tools, the loop, Jev's sufficiency check, the budget, citations and "not found". Use when changing how questions are answered or how the agent moves inside a large PDF.
---

# Navigator

Answers a question the way a person would: pick the folder, open the file, look at the PDF's sections, read the
pages, check if it is enough. There is no index of chunks and no vector search. If you are about to add one, stop:
it breaks rule 2 of `CLAUDE.md`.

The trigram index on node titles (skill `creating-migrations`) serves the person's name filter in the tree. It
matches titles only, never content, and no agent tool uses it: the Navigator finds things by descending.

| Piece | File |
|---|---|
| tools | `navigator/tools.py` |
| loop and budget | `navigator/loop.py` |
| questions to Jev | `navigator/questions.py` |
| citations and the claim check | `navigator/answer.py` |
| progress events to the chat | `navigator/events.py` (`nav.step` on the websocket) |

## Tools

| Tool | Returns |
|---|---|
| `list_folder(node)` | children with kind and description |
| `read_page(node, section?)` | a Markdown page, whole or one section |
| `open_map(pdf)` | the PDF's sections with page ranges (skill `pdf-files`) |
| `read_pages(pdf, first, last)` | the text of those pages, straight from the PDF |
| `page_image(pdf, page)` | the page rendered, for tables and scanned pages |
| `neighbors(pdf, page, n)` | the pages around one page |

## The loop

1. **Route** (one Jev call): intent (`Choice`), which base when asked from the home screen (`Choice`), "does it need
   facts about two different things?" (`Noul`). Two-part questions are split by the LLM and each part runs the loop.
2. **Descend** folders with a `Choice` per level, as the Curator does, but pages **and PDFs** are options. Keep the 2
   best paths.
3. **Open**: a page is read whole (or by section when long). A PDF: `open_map`, then a `Choice` over its sections,
   descending until a range of at most 6 pages.
4. **Read and judge**: read the pages; one Jev call with a `page_answers` `Noul` per page read plus `sufficient`.
5. **Enough?** `sufficient` above the threshold → answer. Otherwise expand, in this order, each a Jev `Choice` over
   the candidates: neighbor pages, sibling sections in the map, the second path of the descent, then a reworded
   question (LLM) and a new descent.
6. **Answer**: LLM `answer` with the kept passages only; split into claims; one `claim_supported` `Noul` per claim;
   unsupported claims are removed.

## Budget (`config.NavigatorBudget`)

At most 3 expansion rounds, 25 pages read, 30 Jev questions per question asked. Out of budget without enough:
"Não encontrei", listing where it looked, with "Procurar no PDF inteiro" and "Ensinar a resposta" (which opens
Capturar with the question).

## Citations

Every claim carries a marker that resolves to a `Citation`: a page with its section anchor, or a PDF with its page
number. The web app opens the original PDF at that page (skill `web-app`).
