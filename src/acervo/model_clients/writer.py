from typing import Protocol

from acervo.domain.cards import Card, CardInput, PatchRequest, WrittenPatch


class Writer(Protocol):
    """Every text the LLM writes, one method per role of `LlmRoles` (skill `llm-calls`). It never decides."""

    async def card(self, source: CardInput) -> Card: ...

    async def patch(self, request: PatchRequest) -> WrittenPatch: ...
