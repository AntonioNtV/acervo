# Interview

Whoever asks carries rules they did not write down. The interview gets them out before they become code. The
script is fixed on purpose: it forces a search for gaps instead of waiting to feel them.

## How to ask

- Read the whole request (and the ticket, if any) before the first round.
- Rounds of up to 4 questions with `AskUserQuestion`, 2 to 4 options each. The first option is your
  recommendation, marked "(Recommended)", with the reason in its description.
- Every question must change something in the spec. If both answers lead to the same spec, do not ask.
- Ask about intent, rules and priority. What the code answers goes to exploration.
- What changes the design most comes first (goal, scope, data); details later. Follow a new thread before
  returning to the script.

## Script

Cover every category; one that does not apply is recorded as "not applicable" with the reason.

1. **Goal.** What problem, for whom (the person writing pages, keeping files, finding something again), and how
   they do it today.
2. **Scope.** What is in and, above all, what is out.
3. **Flow.** The happy path step by step, from the point of view of whoever uses it.
4. **Data.** What is stored, where it comes from, its shape, what happens to existing pages, PDFs, versions and
   links.
5. **Rules.** The rules of `CLAUDE.md` it touches (a PDF stays a PDF, the layers, a migration per table change),
   what goes to the trash and comes back, states and allowed transitions.
6. **Edge cases and errors.** Duplicates, title clashes, another tab editing the same page, huge or protected PDFs,
   trashed parents; what the person sees when it fails.
7. **Integration.** The HTTP contract and the web app. Whether the UI changes together.
8. **Non-functional.** Volume (pages, files, tree depth), latency of a save or a search, file sizes, what must be
   idempotent.
9. **Vocabulary.** The names for the new things. They become names in the code.
10. **Done.** What someone observes (in the UI, in the database) that proves it works.

## When to stop

When every category is answered or "not applicable" and no open question would change the spec. If the engineer
says enough, stop and record what is open as an assumption.

## What to record

`.work/<slug>/interview.md`, grouped by category:

```markdown
## 4. Data
- Q: Do pages already saved get the new field?
  A: Yes, a backfill script fills it for every page without one. (engineer)

## Decisions
- <decision> — discarded: <which and why>

## Assumptions
- <what was left unanswered and the assumption taken>
```
