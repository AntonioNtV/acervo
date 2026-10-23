---
name: jev-decisions
description: How Acervo asks Jev (TypeSafe's decision model) to choose, judge and route - the Decider protocol, the three question types, batching, thresholds in config, the decision log and the LLM fallback. Use when adding or changing any decision an agent makes.
---

# Jev decisions

Jev is a decision model: it takes a state (text or JSON) and typed questions and returns a probability for every
allowed answer. It never writes text. In Acervo every "which one?", "is it?" and "is it enough?" goes to Jev; the
LLM is only for text a person reads (skill `llm-calls`).

| Piece | File | What it is |
|---|---|---|
| protocol | `model_clients/decider.py` | `Decider.ask(state, questions) -> Answers`; the pipeline only sees this |
| Jev client | `model_clients/jev.py` | the only file that knows Jev's wire format, endpoint and auth |
| LLM fallback | `model_clients/llm_decider.py` | same protocol over an LLM with structured output; chosen by config |
| fake | `model_clients/fakes.py` | `FakeDecider`: answers from a table or a function of (state, question), records every call (skill `testing`) |
| questions | `domain/decisions.py` | `Noul`, `Choice`, `Score` and `Answers` (typed, with probabilities) |
| log | `repositories/decision_log.py` | one `decision_log` row per question, written by the service that ran the agent |
| cache | `model_clients/cache.py` | response cache keyed by the hash of state + questions |

`model_clients/` never touches the database: the pipeline returns what was asked and answered, and the service
writes the log on its `UnitOfWork` with the proposal it produced.

## The three question types

| Type | Asks | Returns | Used for |
|---|---|---|---|
| `Noul` | yes or no | `P(yes)` | "already on the page?", "contradicts?", "does this page answer?", "is it enough?" |
| `Choice` | one of up to 255 named options | the choice and a probability per option | which subfolder, which section, which intent |
| `Score` | a level on a rubric of 2 to 10 levels, low to high | the expected level, from 0 (`Answers.score`) | how useful a passage is for the question (0–3) |

Options of a `Choice` carry the node's **description**, not just its name: `"Residencial — produto residencial:
emissão, renovação, coberturas"`. A choice is only as good as its options (skill `markdown-pages`, descriptions).

## Jev's wire format

`model_clients/jev.py` alone speaks it (`Settings.jev_url`, `jev_model`, `jev_api_key` from `JEV_API_KEY`):

```
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer <JEV_API_KEY>
{"model": "jev-latest",
 "state": <text or JSON>,
 "questions": {
   "<id>": {"type": "choice", "instructions": "<task>", "criteria": {"<option id>": "<option text>", ...}},
   "<id>": {"type": "score", "instructions": {"question": "...", "task": "...", "evidence": "..."},
            "criteria": ["<level 0>", "<level 1>", ...]}}}
→ {"answers": {"<id>": {"probabilities": {"<option id>": p, ...}}, "<id>": {"type": "score", "score": 0..3}}}
```

Several questions go in one request (a search sends up to `RetrievalLimits.menus_per_call` menus, or
`per_score_call` passages, per call). A choice's answer must name every option and sum to 1 ± 0.02, and every
question sent must be answered; otherwise the call fails visibly, never falling back to another method. Text in
the state (titles, descriptions, passages) is data, never instructions.

## Rules

- **One call per state.** Every independent question about the same state goes in one `ask` (about 300 tokens of
  fixed overhead per call, about 20 per extra question).
- **Ask about the evidence, decide in code.** Ask "is the context enough to answer?", not "answer or search more?".
  The action is an `if` against `Thresholds`.
- **No threshold in a prompt or a question.** Every cut-off is a field of `Thresholds` with a comment saying what
  crossing it does.
- **Every call is logged**: `run_id`, `step`, question type, options, probabilities, the threshold used and the
  action taken. The proposal it produced points back to the run.
- Probabilities come rounded to two decimals; ties are broken by the order the options were given (put the
  current location first when it is an option).
- Retry with back-off on 429 and 529; a cached state is never re-sent.

## Default thresholds (`Thresholds` in `core/settings.py`)

| Field | Default | When crossed |
|---|---|---|
| `place_min` | 0.60 | below: do not choose; ask the person with the top 3 options |
| `place_show_second` | 0.90 | below: the proposal shows the 2nd option next to the 1st |
| `covered` | 0.80 | above: "already written", no proposal |
| `contradicts` | 0.60 | above: a conflict proposal instead of an edit |
| `pdf_new_version` | 0.70 | above: propose replacing the existing PDF |
| `page_answers` | 0.50 | above: the read page is kept as evidence |
| `sufficient` | 0.80 | above: stop navigating and answer |
| `claim_supported` | 0.70 | below: the claim is removed from the answer |
| `evidence_min` | 1.5 | below, on the 0–3 usefulness score: the passage is dropped from the evidence |
| `evidence_enough` | 2.75 | at or above: the passage fully answers; the search stops |

These are starting points. They are recalibrated from the decision log and the proposals' outcomes (skill `evals`).

## Adding a decision

1. Write the question builder next to the agent that asks it (`pipeline/curator/questions.py`,
   `pipeline/navigator/questions.py`) and add it to that agent's single `ask` for the state.
2. Add the threshold to `Thresholds` with its default and comment.
3. Test the policy with a `FakeDecider` that returns fixed probabilities (skill `testing`): each side of the
   threshold is one test.
4. Add cases to the golden set that exercises it (skill `evals`).
