import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from acervo.core.errors import DecisionUnavailable
from acervo.domain.decisions import Choice, Noul, Score
from acervo.model_clients.jev import DecisionInvalid, JevDecider

FOLDER = Choice(id="folder", question="Em qual pasta?", options=("Residencial — apólices", "Auto — sinistros"))
COVERED = Noul(id="covered", question="Já está escrito na página?")
USEFUL = Score(id="useful", question="Quão útil é o trecho?", levels=("nada", "pouco", "parte", "tudo"))

ANSWERS = {
    "folder": {"probabilities": {"0": 0.7, "1": 0.3}},
    "covered": {"probabilities": {"yes": 0.123, "no": 0.877}},
    "useful": {"type": "score", "score": 2.5},
}


def jev(respond: Callable[[httpx.Request], httpx.Response]) -> tuple[JevDecider, list[httpx.Request]]:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return respond(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return JevDecider("https://jev.test/v1", "jev-latest", "secret", client=client, first_wait=0), sent


def answering(answers: dict[str, Any], status: int = 200) -> Callable[[httpx.Request], httpx.Response]:
    return lambda request: httpx.Response(status, json={"answers": answers})


async def test_a_batch_goes_in_one_request_and_maps_to_answers() -> None:
    decider, sent = jev(answering(ANSWERS))

    answers = await decider.ask("Emissão leva 3 dias úteis", [FOLDER, COVERED, USEFUL])

    assert len(sent) == 1
    assert sent[0].headers["authorization"] == "Bearer secret"
    assert json.loads(sent[0].content) == {
        "model": "jev-latest",
        "state": "Emissão leva 3 dias úteis",
        "questions": {
            "folder": {
                "type": "choice",
                "instructions": "Em qual pasta?",
                "criteria": {"0": "Residencial — apólices", "1": "Auto — sinistros"},
            },
            "covered": {
                "type": "choice",
                "instructions": "Já está escrito na página?",
                "criteria": {"yes": "Sim", "no": "Não"},
            },
            "useful": {"type": "score", "instructions": "Quão útil é o trecho?", "criteria": list(USEFUL.levels)},
        },
    }
    assert answers.probs == {"folder": (0.7, 0.3), "covered": (0.12,), "useful": (2.5,)}
    assert answers.p_yes("covered") == 0.12
    assert answers.score("useful") == 2.5


@pytest.mark.parametrize(
    "answers",
    [
        pytest.param({**ANSWERS, "folder": {"probabilities": {"0": 1.0}}}, id="missing option"),
        pytest.param({**ANSWERS, "folder": {"probabilities": {"0": 0.6, "1": 0.3}}}, id="sum of 0.9"),
        pytest.param({**ANSWERS, "folder": {"probabilities": {"0": 0.7, "1": 0.2, "2": 0.1}}}, id="unknown option"),
        pytest.param({**ANSWERS, "other": {"probabilities": {"yes": 1, "no": 0}}}, id="unknown question"),
        pytest.param({"folder": ANSWERS["folder"], "covered": ANSWERS["covered"]}, id="missing question"),
        pytest.param({**ANSWERS, "useful": {"type": "score", "score": 4}}, id="score of 4 on 4 levels"),
    ],
)
async def test_an_answer_off_the_questions_is_invalid(answers: dict[str, Any]) -> None:
    decider, _ = jev(answering(answers))

    with pytest.raises(DecisionInvalid):
        await decider.ask("Emissão", [FOLDER, COVERED, USEFUL])


async def test_an_overload_is_retried() -> None:
    statuses = iter([529, 529, 200])
    decider, sent = jev(
        lambda request: httpx.Response(next(statuses), json={"answers": {"covered": ANSWERS["covered"]}})
    )

    answers = await decider.ask("Emissão", [COVERED])

    assert len(sent) == 3
    assert answers.p_yes("covered") == 0.12


async def test_a_refused_key_fails_at_once() -> None:
    decider, sent = jev(answering({}, status=401))

    with pytest.raises(DecisionUnavailable) as raised:
        await decider.ask("Emissão", [COVERED])

    assert len(sent) == 1
    assert not isinstance(raised.value, DecisionInvalid)


async def test_a_cached_state_is_not_sent_again() -> None:
    decider, sent = jev(answering({"covered": ANSWERS["covered"]}))

    first = await decider.ask("Emissão", [COVERED])
    second = await decider.ask("Emissão", [COVERED])

    assert len(sent) == 1
    assert second.cached and second.probs == first.probs
