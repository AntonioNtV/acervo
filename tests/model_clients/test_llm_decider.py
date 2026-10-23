from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from acervo.domain.decisions import Choice, Noul
from acervo.model_clients.llm_decider import LlmDecider

FOLDER = Choice(id="folder", question="Em qual pasta?", options=("Residencial — apólices", "Auto — sinistros", "Vida"))
COVERED = Noul(id="covered", question="Já está escrito na página?")


def answering(answers: list[dict[str, Any]], calls: list[str]) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(str(messages[-1]))
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"answers": answers})])

    return FunctionModel(respond)


async def test_probabilities_are_normalized_and_rounded() -> None:
    calls: list[str] = []
    model = answering(
        [{"id": "folder", "probabilities": [0.6, 0.2, 0.4]}, {"id": "covered", "probabilities": [0.333]}], calls
    )

    answers = await LlmDecider(model).ask("Emissão leva 3 dias úteis", [FOLDER, COVERED])

    assert answers.probs == {"folder": (0.5, 0.17, 0.33), "covered": (0.33,)}
    assert answers.winner("folder") == "Residencial — apólices"
    assert not answers.cached
    assert len(calls) == 1


async def test_a_tie_keeps_the_order_the_options_were_given() -> None:
    model = answering([{"id": "folder", "probabilities": [0.1, 0.45, 0.45]}], [])

    answers = await LlmDecider(model).ask("Sinistro de carro", [FOLDER])

    assert answers.ranked("folder")[:2] == [("Auto — sinistros", 0.45), ("Vida", 0.45)]


async def test_a_cached_state_is_not_sent_again() -> None:
    calls: list[str] = []
    decider = LlmDecider(answering([{"id": "covered", "probabilities": [0.9]}], calls))

    first = await decider.ask("Emissão leva 3 dias úteis", [COVERED])
    second = await decider.ask("Emissão leva 3 dias úteis", [COVERED])

    assert len(calls) == 1
    assert second.cached and second.probs == first.probs
