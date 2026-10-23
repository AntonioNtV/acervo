"""The questions asked of the decision model and its answers (skill `jev-decisions`)."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Noul(BaseModel):
    """A yes-or-no question about the state; answered with P(yes)."""

    model_config = ConfigDict(frozen=True)

    type: Literal["noul"] = "noul"
    id: str
    question: str


class Choice(BaseModel):
    """One of up to 255 named options; answered with a probability per option, in the options' order."""

    model_config = ConfigDict(frozen=True)

    type: Literal["choice"] = "choice"
    id: str
    question: str
    # Each option carries the node's description, not just its name.
    options: tuple[str, ...] = Field(min_length=1, max_length=255)


Question = Annotated[Noul | Choice, Field(discriminator="type")]


class Answers(BaseModel):
    """What the decider answered for one state: per question, one probability per option (a Noul's is P(yes))."""

    model_config = ConfigDict(frozen=True)

    questions: tuple[Question, ...]
    probs: dict[str, tuple[float, ...]]
    latency_ms: int = 0
    cached: bool = False

    @model_validator(mode="after")
    def _one_probability_per_option(self) -> Self:
        for question in self.questions:
            expected = len(question.options) if isinstance(question, Choice) else 1
            got = len(self.probs.get(question.id, ()))
            if got != expected:
                raise ValueError(f"question {question.id!r} needs {expected} probabilities, got {got}")
        return self

    def question(self, id: str) -> Question:
        return next(question for question in self.questions if question.id == id)

    def ranked(self, id: str) -> list[tuple[str, float]]:
        """A Choice's options from the most likely down; a tie keeps the order the options were given."""
        question = self.question(id)
        if not isinstance(question, Choice):
            raise TypeError(f"question {id!r} is not a Choice")
        return sorted(zip(question.options, self.probs[id], strict=True), key=lambda pair: -pair[1])

    def winner(self, id: str) -> str:
        return self.ranked(id)[0][0]

    def p_yes(self, id: str) -> float:
        if not isinstance(self.question(id), Noul):
            raise TypeError(f"question {id!r} is not a Noul")
        return self.probs[id][0]
