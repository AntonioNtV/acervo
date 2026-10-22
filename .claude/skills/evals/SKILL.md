---
name: evals
description: Measuring Acervo's decisions on real data - golden sets for placement and answers, the runner, the metrics and recalibrating thresholds from the decision log and proposal outcomes. Use before changing a prompt, a question, an option text or a threshold, and to compare Jev with the LLM fallback.
---

# Evals

Tests prove the policy; evals measure whether the decisions are right. A change to a prompt, a question, how
options are described or a threshold is not done until its eval ran before and after.

| Set | File | One case is |
|---|---|---|
| text placement | `evals/placement.jsonl` | a message, the tree, the expected page and section (or "new page in <folder>") |
| PDF placement | `evals/pdf_placement.jsonl` | a PDF in `evals/pdfs/`, the tree, the expected folder |
| answers | `evals/qa.jsonl` | a question, the base, the expected citations (page/anchor or PDF/page), or `not_found` |
| conflicts | `evals/conflicts.jsonl` | a message and a page, whether it contradicts |

Start with 50 real messages and 30 real PDFs from the person's own work; synthetic cases only fill gaps.

```bash
cd python
uv run acervo evals run placement --decider jev
uv run acervo evals run placement --decider llm      # same cases, LLM fallback
uv run acervo evals run qa
uv run acervo evals calibrate                         # from decision_log + proposal outcomes
```

Results go to `evals/results/<date>-<set>-<decider>.json`; the runner prints a comparison with the previous run.

## Metrics

| Metric | Set | Target to start |
|---|---|---|
| right place, first path | placement | 80% |
| right place, first or second path | placement | 92% |
| asked the person when it should have | placement | below `place_min` on 90% of the wrong ones |
| answer cites the expected source | qa | 85% |
| said "not found" when it should | qa | 90% |
| pages read per answer | qa | median at most 8 |

## Calibrating thresholds

`evals calibrate` joins every logged decision with what the person did to the proposal it produced (accepted,
edited, rejected with a reason) and prints, per threshold, the accuracy and coverage at each cut-off. Change the
default in `config.Thresholds` only from that table, and write the run's file name in the commit message.
