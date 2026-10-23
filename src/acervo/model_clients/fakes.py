"""Stand-ins for the decision model and the LLM: tests never call either (skill `testing`)."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from acervo.domain.cards import Card, CardInput, ChildDescription, PatchRequest, WrittenPatch
from acervo.domain.decisions import Answers, Choice, Question

# A Noul's P(yes) or a Score's expected level; a Choice's probabilities in its options' order, or by option text
# (missing options get 0).
FakeProbs = float | Sequence[float] | Mapping[str, float]


@dataclass
class FakeDecider:
    """Answers from a table keyed by question id, else from `answer(state, question)` for ids made at run time
    (a search's menus and passages); records every call as (state, questions)."""

    table: dict[str, FakeProbs] = field(default_factory=dict)
    answer: Callable[[str, Question], FakeProbs] | None = None
    calls: list[tuple[str, list[Question]]] = field(default_factory=list)

    async def ask(self, state: str, questions: Sequence[Question]) -> Answers:
        self.calls.append((state, list(questions)))
        return Answers(questions=tuple(questions), probs={q.id: self._probs(state, q) for q in questions})

    def _probs(self, state: str, question: Question) -> tuple[float, ...]:
        if question.id in self.table:
            answer = self.table[question.id]
        elif self.answer is not None:
            answer = self.answer(state, question)
        else:
            raise KeyError(f"FakeDecider has no answer for question {question.id!r}")
        if isinstance(answer, int | float):
            return (float(answer),)
        if isinstance(answer, Mapping):
            options = question.options if isinstance(question, Choice) else ()
            return tuple(answer.get(option, 0.0) for option in options)
        return tuple(answer)


@dataclass
class FakeWriter:
    """Gives a fixed output per role and records the inputs of every call under the role's name."""

    card_output: Card = field(default_factory=lambda: Card(title="Nota", subject="Uma nota"))
    patch_output: WrittenPatch = field(default_factory=lambda: WrittenPatch(lines=["- Uma nota"]))
    describe_output: str = "Descrição"
    inputs: dict[str, list[Any]] = field(default_factory=dict)

    async def card(self, source: CardInput) -> Card:
        self._record("card", source)
        return self.card_output

    async def patch(self, request: PatchRequest) -> WrittenPatch:
        self._record("patch", request)
        return self.patch_output

    async def describe(self, title: str, children: Sequence[ChildDescription]) -> str:
        self._record("describe", (title, list(children)))
        return self.describe_output

    def _record(self, role: str, value: Any) -> None:
        self.inputs.setdefault(role, []).append(value)
