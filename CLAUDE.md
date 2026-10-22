# Acervo

Knowledge bases in the style of Notion, with a side chat that files what you drop in it. A PDF is saved in the
right folder; a thing you learned becomes a proposed edit to the right Markdown page; a question is answered by
navigating folders and the pages of PDFs. The LLM writes, Jev decides, code applies the policy, the person approves.

## Rules the code never breaks

1. **A PDF stays a PDF.** It is saved, moved, renamed or replaced by a newer version. It is never converted to
   Markdown, never becomes a page, never gets copied into one. (skill `pdf-files`)
2. **No chunks, no embeddings, no vector store.** Retrieval is navigation: descend folders, open a file, read whole
   pages. (skill `navigator-agent`)
3. **Nothing is written without the person.** Agents produce proposals; only an accepted proposal changes a base.
   (skill `proposals`)
4. **Jev decides, the LLM writes, code decides what a probability means.** Thresholds live in config, never in a
   prompt. (skills `jev-decisions`, `llm-calls`)
5. **Every decision is logged** with its options and probabilities, linked to the proposal it produced.

## Conventions

- Every non-trivial change follows skill `feature-flow`: interview, spec ✋, cards ✋, `senior-engineer` agents in
  worktrees, `ponytail:ponytail-review` and the `reviewer` agent. No code before the cards are approved.
- Code, identifiers, commits, tests and skills in English. Text the person reads in the app is pt-BR (i18n).
- A comment only for the why the code does not show. No new markdown files besides skills.
- `.work/` holds the feature flow's files and never goes into git.
- Conventional Commits: `feat(<area>): …`, `fix(<area>): …`.

## Skills

| Skill | Use when |
|---|---|
| `repo-structure` | deciding where new code goes, or reading an unfamiliar area |
| `feature-flow` | any non-trivial change: interview, spec, cards, parallel implementation |
| `jev-decisions` | adding or changing a decision (route, choose, judge) |
| `llm-calls` | adding or changing something the LLM writes |
| `curator-agent` | where and how a dropped PDF or a learned fact is filed |
| `navigator-agent` | how a question is answered by navigation |
| `pdf-files` | anything that touches a PDF: upload, map, reading pages, versions |
| `markdown-pages` | pages, sections, versions, descriptions of nodes |
| `proposals` | the proposal lifecycle, diffs, accept, reject, rebase |
| `http-contract` | a route, a request/response model, an error, the generated client |
| `creating-migrations` | any change to the tables |
| `testing` | writing or running a Python test |
| `evals` | measuring placement and answers, calibrating thresholds |
| `ui-design` | designing or changing a screen |
| `web-app` | the React app: structure, checks, editor, PDF viewer, chat |

Design boards: https://claude.ai/artifact/Jjq3r6SPUZ9E4jUG7WtqGR (canvas "Acervo · Interface").
