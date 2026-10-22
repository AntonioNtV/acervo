# Parallel implementation and integration

You orchestrate: you do not implement cards, you hand them out, integrate and verify. Agents writing at the same
time make implicit decisions that contradict each other; that is why contracts are locked in wave 0 and every
agent has exclusive files. Parallelism is expensive: a wave with one card, or with cards that depend on each other,
goes to a single agent.

Mechanical mass work (moving code, renaming, rewriting imports) does not go to agents: it becomes a deterministic
script, run first on a throwaway copy (`git worktree add --detach`) and proven by an automatic check (the same test
suite passing).

## Before starting

- Create the feature branch from an up-to-date `main`: `feat/<slug>`.
- Worktrees live next to the repo, one per card, branched from the feature branch:

  ```bash
  git worktree add ../acervo-worktrees/card-NN -b card/NN-<slug> feat/<slug>
  ```

  Only what is committed on the feature branch reaches them; `.work/` does not, so the brief gives absolute paths
  to the card and the spec.

## Each wave (wave 0 first, alone)

In a single message, launch one `Agent` with `subagent_type: "senior-engineer"` per card, up to 5; when a wave has
more, launch the next as one returns. The brief is short, the card has everything:

```
Card: <abs path>/.work/<slug>/cards/<NN-slug>.md
Spec (context, not scope): <abs path>/.work/<slug>/spec.md
Worktree: <abs path>/acervo-worktrees/card-NN (branch card/NN-<slug>, from feat/<slug> @ <hash>). Work only there.
```

Mark the cards `doing`.

## When an agent returns

**BLOCKED.** Take the question to the engineer with the agent's recommendation, record the answer in the card and
relaunch a new agent on the same worktree (a finished agent resumed with `SendMessage` may lose its shell).

**DONE.** Integrate one at a time:

1. Check what really changed, not the report: `git log --stat feat/<slug>..card/NN-<slug>`. A file outside the
   card's list goes back to the agent.
2. `git merge --no-ff card/NN-<slug>` on the feature branch.
3. Checks on the integrated code, from the repository root:
   ```bash
   uv run ruff check && uv run ruff format --check
   uv run pytest tests/<card areas>
   ```
   A card in `web/`: the checks of skill `web-app`. A card that changes a decision: its eval (skill `evals`).
4. Failed: send the output to a new agent on the same worktree. A one-line fix you make yourself.
5. Green: card `status: done`, `branch: <name>`; `git worktree remove ../acervo-worktrees/card-NN` and
   `git branch -d card/NN-<slug>`.

Open the next wave only with the current one integrated and green: the new worktrees must start from it.

## Closing

1. `uv run pytest` (the whole suite; it is fast).
2. `ponytail:ponytail-review` over `git diff main...HEAD`; apply the cuts that do not change the spec's behavior;
   rerun the tests if you cut.
3. Launch an `Agent` with `subagent_type: "reviewer"`, giving the feature folder and the base branch (`main`).
4. Fix the findings that hold; say why for the ones you reject. At most two review rounds.
5. Deliver to the engineer what each card became, the tests and their result, what you did not verify and the
   findings you did not apply.
