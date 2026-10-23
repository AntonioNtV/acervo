import pytest

from acervo.core.settings import Thresholds
from acervo.domain.cards import ROUTES, Route
from acervo.model_clients.fakes import FakeDecider, FakeWriter
from acervo.pipeline.router import AskFirst, RouteContext, Routed, Split, route
from acervo.schemas.proposal import Decision


def _intent(winner: Route, probability: float) -> list[float]:
    rest = (1 - probability) / (len(ROUTES) - 1)
    return [probability if r == winner else rest for r in ROUTES]


@pytest.mark.parametrize("intent", ROUTES)
async def test_each_intent_is_understood_in_one_call(
    intent: Route, fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    fake_decider.table = {"intent": _intent(intent, 0.85), "two_subjects": 0.1}
    log: list[Decision] = []

    understood = await route("Emissão leva 3 dias úteis", RouteContext(), fake_decider, fake_writer, thresholds, log)

    assert understood == Routed(text="Emissão leva 3 dias úteis", route=intent, probability=0.85)
    assert [q.id for q in fake_decider.calls[0][1]] == ["intent", "two_subjects"]
    assert len(fake_decider.calls) == 1
    assert [(d.step, d.threshold, d.action) for d in log] == [
        ("route", thresholds.route_min, intent),
        ("route", thresholds.route_split, "whole"),
    ]


async def test_below_route_min_asks_between_the_two_likeliest(
    fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    fake_decider.table = {"intent": [0.45, 0.4, 0.1, 0.05], "two_subjects": 0.1}

    understood = await route("tabela auto 2025", RouteContext(), fake_decider, fake_writer, thresholds, [])

    assert understood == AskFirst(text="tabela auto 2025", options=("perguntar", "guardar"))


async def test_above_route_split_each_part_is_understood(
    fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    fake_decider.table = {"intent": _intent("guardar", 0.9), "two_subjects": 0.8}
    fake_writer.split_output = ["Emissão leva 3 dias úteis", "O Itaú aceita boleto"]
    log: list[Decision] = []

    understood = await route(
        "Emissão leva 3 dias úteis e o Itaú aceita boleto", RouteContext(), fake_decider, fake_writer, thresholds, log
    )

    assert understood == Split(
        parts=[
            Routed(text="Emissão leva 3 dias úteis", route="guardar", probability=0.9),
            Routed(text="O Itaú aceita boleto", route="guardar", probability=0.9),
        ]
    )
    assert fake_writer.inputs["split_message"] == ["Emissão leva 3 dias úteis e o Itaú aceita boleto"]
    assert [[q.id for q in questions] for _, questions in fake_decider.calls] == [
        ["intent", "two_subjects"],
        ["intent"],
        ["intent"],
    ]
    assert log[1].action == "split"


async def test_a_bare_file_is_guardar_without_asking(
    fake_decider: FakeDecider, fake_writer: FakeWriter, thresholds: Thresholds
) -> None:
    context = RouteContext(files=["CG 2026.pdf"])

    understood = await route("  ", context, fake_decider, fake_writer, thresholds, [])

    assert understood == Routed(text="  ", route="guardar", probability=1.0)
    assert fake_decider.calls == []
