from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from acervo.core.settings import LlmRoles
from acervo.domain.cards import Card, CardInput, PatchRequest, WrittenPatch
from acervo.model_clients.llm_writer import InvalidOutput, LlmWriter

CARD = Card(title="Prazo de emissão", subject="Emissão leva 3 dias úteis", facts=["Emissão leva 3 dias úteis"])


def writer_with(model: Any) -> LlmWriter:
    return LlmWriter(dict.fromkeys(LlmRoles.model_fields, model))


def replies(*outputs: dict[str, Any], calls: list[int]) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, outputs[len(calls) - 1])])

    return FunctionModel(respond)


async def test_each_role_returns_its_validated_output() -> None:
    writer = writer_with(TestModel())

    assert isinstance(await writer.card(CardInput(text="Emissão leva 3 dias úteis")), Card)
    assert isinstance(
        await writer.patch(PatchRequest(section_markdown="- Vistoria", heading="Prazos", action="append", card=CARD)),
        WrittenPatch,
    )


async def test_an_invalid_output_is_retried_once() -> None:
    calls: list[int] = []
    writer = writer_with(replies({"title": "x"}, CARD.model_dump(), calls=calls))

    assert await writer.card(CardInput(text="Emissão leva 3 dias úteis")) == CARD
    assert len(calls) == 2


async def test_a_second_invalid_output_raises_with_the_raw_text() -> None:
    calls: list[int] = []
    writer = writer_with(replies({"title": "x"}, {"title": "y" * 20}, calls=calls))

    with pytest.raises(InvalidOutput) as raised:
        await writer.card(CardInput(text="Emissão leva 3 dias úteis"))

    assert len(calls) == 2
    assert raised.value.role == "card"
    assert "y" * 20 in raised.value.raw
