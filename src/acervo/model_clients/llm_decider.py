"""The `Decider` over an LLM with structured output, the fallback to Jev chosen by config (skill `jev-decisions`)."""

import time
from collections.abc import Sequence
from typing import Annotated

from pydantic import BaseModel, Field
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.models import Model

from acervo.domain.decisions import Answers, Choice, Question, Score
from acervo.model_clients.cache import DecisionCache
from acervo.model_clients.llm_writer import make_agent, prompt, run


class _Answer(BaseModel):
    id: str = Field(description="The question's id.")
    probabilities: list[Annotated[float, Field(ge=0)]] = Field(
        description="A choice: one per option, in the options' order. A yes-or-no question: only P(yes). "
        "A score: only the expected level, from 0."
    )


class _Answers(BaseModel):
    answers: list[_Answer]


def _check(ctx: RunContext[Sequence[Question]], output: _Answers) -> _Answers:
    given = {answer.id: answer.probabilities for answer in output.answers}
    for question in ctx.deps:
        expected = len(question.options) if isinstance(question, Choice) else 1
        probs = given.get(question.id)
        if probs is None or len(probs) != expected:
            raise ModelRetry(f"question {question.id!r} needs exactly {expected} probabilities")
        if isinstance(question, Choice) and sum(probs) == 0:
            raise ModelRetry(f"question {question.id!r}: the probabilities cannot all be 0")
        top = len(question.levels) - 1 if isinstance(question, Score) else 1
        if not all(p <= top for p in probs):
            raise ModelRetry(f"question {question.id!r}: each value goes from 0 to {top}")
    return output


class LlmDecider:
    """Every question about one state in one call; a Choice's probabilities normalized to sum to 1."""

    def __init__(self, model: Model | str, cache: DecisionCache | None = None) -> None:
        self._agent = make_agent(model, _Answers, deps_type=Sequence[Question])
        self._agent.output_validator(_check)
        self._prompt = prompt("decide")
        self._cache = cache or DecisionCache()

    async def ask(self, state: str, questions: Sequence[Question]) -> Answers:
        key = DecisionCache.key(state, questions)
        if (cached := self._cache.get(key)) is not None:
            return cached.model_copy(update={"cached": True})
        started = time.perf_counter()
        output: _Answers = await run(
            "decide", self._agent, self._prompt.format_map({"state": state, "questions": _render(questions)}), questions
        )
        given = {answer.id: answer.probabilities for answer in output.answers}
        answers = Answers(
            questions=tuple(questions),
            probs={question.id: _normalized(question, given[question.id]) for question in questions},
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        self._cache.put(key, answers)
        return answers


def _normalized(question: Question, probs: list[float]) -> tuple[float, ...]:
    if isinstance(question, Choice):
        total = sum(probs)
        probs = [p / total for p in probs]
    return tuple(round(p, 2) for p in probs)


def _render(questions: Sequence[Question]) -> str:
    lines = []
    for question in questions:
        if isinstance(question, Choice):
            lines.append(f"[{question.id}] (escolha) {question.question}")
            lines.extend(f"  {number}. {option}" for number, option in enumerate(question.options, 1))
        elif isinstance(question, Score):
            lines.append(f"[{question.id}] (nota) {question.question}")
            lines.extend(f"  {level}. {text}" for level, text in enumerate(question.levels))
        else:
            lines.append(f"[{question.id}] (sim ou não) {question.question}")
    return "\n".join(lines)
