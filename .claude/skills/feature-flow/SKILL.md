---
name: feature-flow
description: The flow of every non-trivial change in Acervo - interview whoever asked, explore the code, a spec the engineer approves, cards the engineer approves, implementation by up to 5 senior-engineer agents in parallel worktrees, integration and review. Use when asked for a feature, a behavior change or a bug without a single obvious fix.
---

# Feature flow

```
0 triage → 1 interview → 2 exploration → 3 spec ✋ → 4 cards ✋ → 5 implementation → 6 integration and review
```

✋ is the engineer's approval. Nothing moves without it, and no code before step 5.

**Ponytail full from start to end** (skill `ponytail:ponytail`, `full`): what does not need to exist leaves the
spec, cards ask for the smallest diff, implementation reuses what the code has.

Everything the flow writes goes in `.work/<YYYY-MM-DD>-<slug>/` at the repo root, which never goes into git. If the
session drops, resume from that folder: the cards' `status` says what is done.

## 0. Triage

| Size | When | Path |
|---|---|---|
| Trivial | typo, rename, a bug with one obvious fix | do it, no flow |
| S | fits one card: one concept, no migration, no change to the contract | short flow |
| Normal | everything else | full flow |

In doubt, take the bigger size and say so. **Short flow**: interview only the categories that apply; spec and card
are one `spec.md` with a "Card" section at the end, one approval; you implement it yourself and close with the
checks and the `reviewer` of step 6.

## 1. Interview

Follow [interview.md](interview.md): rounds of up to 4 questions with `AskUserQuestion`, each with your recommended
answer; ask about intent, rules and priority, never what reading the code answers. Record in `interview.md`.

## 2. Exploration

Read what the feature touches before designing: the screen, the route, the service and the layers under it, the
repositories, the tests covering the area and the closest similar feature (it becomes the exemplar). Skill
`repo-structure` says where things live. For wide sweeps, use `Explore` agents in parallel and keep the conclusion.

Record in `exploration.md`, short: what exists, what changes per concept, the exemplar file of each, risks (the rules
in `CLAUDE.md`, the contract, stored versions and files). Then a **second round of questions**, technical: only the
forks the code did not decide, each with a recommendation and the cost of each path.

## 3. Spec ✋

Write `spec.md` from [templates/spec.md](templates/spec.md): what and why, one page, no file or class names. Show
the path and a five-line summary; ask for approval. When approved, fill `approved_on`. From then on the spec
changes only with the engineer.

## 4. Cards ✋

Split the spec into cards from [templates/card.md](templates/card.md), one file each in `cards/NN-slug.md`.

- **Wave 0** holds what the others consume: migration, models, settings, shared Pydantic models, the regenerated
  API client. It runs alone, first.
- **Exclusive files.** Two cards of the same wave never touch the same file. Files everyone edits
  (`core/settings.py`, `db/models/__init__.py`, `repositories/uow.py`, `api/main.py`) go in wave 0
  or in a final wiring card.
- **Size.** One card is one concept or a thin slice. More than 10 cards is two features.
- **Tests are decided here.** Each card names the tests and where (skill `testing`, or `ui-web` for `web/`), or
  "none" and why.

Before showing: every behavior of the spec lands in a card, and no file appears in two cards of one wave. Show a
table (id, title, wave, depends on, tests) and ask for approval. Approving the cards authorizes local commits on
the feature branch; push only when the engineer asks.

## 5. Implementation

Follow [parallel.md](parallel.md). You orchestrate; every card, wave 0 included, goes to a `senior-engineer` agent
in its own worktree, up to 5 at a time.

## 6. Integration and review

Integrate each branch, run the checks, open the next wave only when the current one is green. At the end,
`ponytail:ponytail-review` over the integrated diff and a clean-context `reviewer` agent against the spec and cards.
Details in [parallel.md](parallel.md).

Deliver: what each card became, the tests run and their result, what you did not verify, the reviewer's findings
you did not apply. `.work/` is not in git, so the why lives in the PR description: the problem, the spec's whole
"Decisions" section and the tests that ran.
