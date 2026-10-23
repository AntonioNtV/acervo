"""The `Decider` over Jev's API: the only code that knows its wire format, endpoint and auth (skill `jev-decisions`)."""

import asyncio
import time
from collections.abc import Sequence
from typing import Any

import httpx

from acervo.core.errors import DecisionUnavailable
from acervo.domain.decisions import Answers, Choice, Noul, Question, Score
from acervo.model_clients.cache import DecisionCache

ATTEMPTS = 3
FIRST_WAIT = 0.5
SUM_TOLERANCE = 0.02
# A Noul has no wire type of its own: it goes as a choice between these two.
YES_NO = {"yes": "Sim", "no": "Não"}


class DecisionInvalid(DecisionUnavailable):
    """Jev answered, but not every question sent, or an answer is off its options or levels."""


class JevDecider:
    """Every question about one state in one request; answers checked, never repaired."""

    def __init__(
        self,
        url: str,
        model: str,
        api_key: str,
        cache: DecisionCache | None = None,
        client: httpx.AsyncClient | None = None,
        first_wait: float = FIRST_WAIT,
    ) -> None:
        self._url = url
        self._model = model
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._cache = cache or DecisionCache()
        self._client = client or httpx.AsyncClient(timeout=60)
        self._first_wait = first_wait

    async def ask(self, state: str, questions: Sequence[Question]) -> Answers:
        key = DecisionCache.key(state, questions)
        if (cached := self._cache.get(key)) is not None:
            return cached.model_copy(update={"cached": True})
        started = time.perf_counter()
        body = {"model": self._model, "state": state, "questions": {q.id: _wire(q) for q in questions}}
        given = await self._post(body)
        if not isinstance(given, dict) or set(given) != {q.id for q in questions}:
            raise DecisionInvalid("Jev did not answer exactly the questions sent.", details={"answers": given})
        answers = Answers(
            questions=tuple(questions),
            probs={q.id: _read(q, given[q.id]) for q in questions},
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        self._cache.put(key, answers)
        return answers

    async def _post(self, body: dict[str, Any]) -> Any:
        for attempt in range(ATTEMPTS):
            try:
                response = await self._client.post(self._url, json=body, headers=self._headers)
            except httpx.TransportError as error:
                raise DecisionUnavailable(f"Jev could not be reached: {error}") from error
            transient = response.status_code in (429, 529) or response.status_code >= 500
            if transient and attempt < ATTEMPTS - 1:
                await asyncio.sleep(self._first_wait * 2**attempt)
                continue
            if response.is_error:
                raise DecisionUnavailable(
                    f"Jev refused the request ({response.status_code}).", details={"status": response.status_code}
                )
            try:
                return response.json()["answers"]
            except (ValueError, KeyError, TypeError) as error:
                raise DecisionInvalid("Jev's response has no answers.") from error
        raise AssertionError("unreachable")


def _options(question: Choice | Noul) -> dict[str, str]:
    if isinstance(question, Noul):
        return YES_NO
    return {str(index): option for index, option in enumerate(question.options)}


def _wire(question: Question) -> dict[str, Any]:
    if isinstance(question, Score):
        return {"type": "score", "instructions": question.question, "criteria": list(question.levels)}
    return {"type": "choice", "instructions": question.question, "criteria": _options(question)}


def _read(question: Question, answer: Any) -> tuple[float, ...]:
    if isinstance(question, Score):
        score = answer.get("score") if isinstance(answer, dict) else None
        if not isinstance(score, int | float) or not 0 <= score <= len(question.levels) - 1:
            raise DecisionInvalid(f"Jev's score for {question.id!r} is off its levels.", details={"answer": answer})
        return (round(score, 2),)
    probs = answer.get("probabilities") if isinstance(answer, dict) else None
    ids = list(_options(question))
    if (
        not isinstance(probs, dict)
        or set(probs) != set(ids)
        or not all(isinstance(p, int | float) and 0 <= p <= 1 for p in probs.values())
        or abs(sum(probs.values()) - 1) > SUM_TOLERANCE
    ):
        raise DecisionInvalid(
            f"Jev's probabilities for {question.id!r} do not cover its options or sum to 1.", details={"answer": answer}
        )
    if isinstance(question, Noul):
        return (round(probs["yes"], 2),)
    return tuple(round(probs[id], 2) for id in ids)
