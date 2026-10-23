from collections.abc import Sequence
from typing import Protocol

from acervo.domain.cards import Card, CardInput, ChildDescription, PatchRequest, WrittenPatch


class Writer(Protocol):
    """Every text the LLM writes, one method per role of `LlmRoles` (skill `llm-calls`). It never decides."""

    async def card(self, source: CardInput) -> Card: ...

    async def patch(self, request: PatchRequest) -> WrittenPatch: ...

    async def describe(self, title: str, children: Sequence[ChildDescription]) -> str:
        """A description of a folder or page of at most 200 characters, from its children."""
        ...
