from collections.abc import Sequence
from typing import Protocol

from acervo.domain.cards import Card, CardInput, ChildDescription, PatchRequest, WrittenPatch
from acervo.domain.decisions import Answers


class Writer(Protocol):
    """Every text the LLM writes, one method per role of `LlmRoles` (skill `llm-calls`). It never decides."""

    async def card(self, source: CardInput) -> Card: ...

    async def patch(self, request: PatchRequest) -> WrittenPatch: ...

    async def split_message(self, text: str) -> list[str]:
        """The parts of a message about more than one thing, each standing on its own."""
        ...

    async def describe(self, title: str, children: Sequence[ChildDescription]) -> str:
        """A description of a folder or page of at most 200 characters, from its children."""
        ...

    async def explain(self, answers: Answers) -> str:
        """One sentence saying why, from the logged probabilities; it never re-decides."""
        ...
