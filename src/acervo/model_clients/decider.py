from collections.abc import Sequence
from typing import Protocol

from acervo.domain.decisions import Answers, Question


class Decider(Protocol):
    """Answers typed questions about one state with a probability per option (skill `jev-decisions`).

    Every independent question about the same state goes in one call. Probabilities come rounded to two decimals.
    """

    async def ask(self, state: str, questions: Sequence[Question]) -> Answers: ...
