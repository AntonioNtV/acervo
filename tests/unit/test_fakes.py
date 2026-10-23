import pytest

from acervo.domain.cards import Card, CardInput, ChildDescription
from acervo.domain.decisions import Choice, Noul
from acervo.model_clients.decider import Decider
from acervo.model_clients.fakes import FakeDecider, FakeWriter
from acervo.model_clients.writer import Writer

INTENT = Choice(id="intent", question="O que a pessoa quer?", options=("perguntar", "guardar", "organizar"))
TWO = Noul(id="two_subjects", question="A mensagem fala de duas coisas?")
SECTION = Choice(id="section", question="Qual seção?", options=("Documentos", "Prazos", "Contatos"))


async def test_fake_decider_answers_from_its_table_and_records() -> None:
    decider: Decider = FakeDecider({"intent": [0.1, 0.8, 0.1], "two_subjects": 0.2, "section": {"Prazos": 0.9}})

    answers = await decider.ask("Emissão leva 3 dias úteis", [INTENT, TWO, SECTION])

    assert answers.winner("intent") == "guardar"
    assert answers.p_yes("two_subjects") == 0.2
    assert answers.ranked("section") == [("Prazos", 0.9), ("Documentos", 0.0), ("Contatos", 0.0)]
    assert isinstance(decider, FakeDecider)
    assert decider.calls == [("Emissão leva 3 dias úteis", [INTENT, TWO, SECTION])]


async def test_fake_decider_refuses_a_question_not_in_its_table() -> None:
    with pytest.raises(KeyError, match="covered"):
        await FakeDecider().ask("estado", [Noul(id="covered", question="Já está escrito?")])


async def test_fake_writer_records_inputs_per_role() -> None:
    card = Card(title="Prazo de emissão", subject="Emissão leva 3 dias úteis")
    writer: Writer = FakeWriter(card_output=card)
    source = CardInput(text="Emissão leva 3 dias úteis")
    children = [ChildDescription(title="Residencial", kind="folder", description="produto residencial")]

    assert await writer.card(source) == card
    assert await writer.describe("Bradesco", children) == "Descrição"

    assert isinstance(writer, FakeWriter)
    assert writer.inputs == {
        "card": [source],
        "describe": [("Bradesco", children)],
    }
