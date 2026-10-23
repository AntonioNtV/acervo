import pytest
from pydantic import ValidationError

from acervo.domain.decisions import Answers, Choice, Noul, Score
from acervo.domain.index import Block, DocIndex, DocStats, Passage, Section

PLACE = Choice(id="place", question="Onde guardar?", options=("Bradesco", "Itaú", "Porto"))
COVERED = Noul(id="covered", question="Já está escrito na página?")
USEFUL = Score(id="useful", question="Quanto o trecho ajuda?", levels=("Nada", "Mesmo assunto", "Em parte", "Responde"))


def test_choice_keeps_option_order_on_ties() -> None:
    answers = Answers(questions=(PLACE,), probs={"place": (0.4, 0.2, 0.4)})

    assert answers.winner("place") == "Bradesco"
    assert answers.ranked("place") == [("Bradesco", 0.4), ("Porto", 0.4), ("Itaú", 0.2)]


def test_answers_expose_the_winner_and_probabilities() -> None:
    answers = Answers(questions=(PLACE, COVERED), probs={"place": (0.1, 0.7, 0.2), "covered": (0.85,)})

    assert answers.winner("place") == "Itaú"
    assert answers.ranked("place")[1] == ("Porto", 0.2)
    assert answers.p_yes("covered") == 0.85
    with pytest.raises(TypeError):
        answers.p_yes("place")


def test_answers_need_one_probability_per_option() -> None:
    with pytest.raises(ValidationError):
        Answers(questions=(PLACE,), probs={"place": (0.5, 0.5)})


def test_a_score_is_answered_with_a_level_within_its_rubric() -> None:
    answers = Answers(questions=(USEFUL, COVERED), probs={"useful": (2.8,), "covered": (0.1,)})

    assert answers.score("useful") == 2.8
    with pytest.raises(TypeError):
        answers.score("covered")
    for outside in (-0.1, 3.1):
        with pytest.raises(ValidationError, match="outside"):
            Answers(questions=(USEFUL,), probs={"useful": (outside,)})
    with pytest.raises(ValidationError):
        Score(id="useful", question="Ajuda?", levels=("Sim",))


def test_a_doc_index_round_trips_through_json() -> None:
    index = DocIndex(
        version=1,
        source="pdf",
        outline="Coberturas\n  Incêndio",
        sections=[
            Section(
                id="s1",
                title="Coberturas",
                level=1,
                page=3,
                end_page=5,
                block_ids=["b1"],
                children=[Section(id="s2", title="Incêndio", level=2, page=4, end_page=5, block_ids=["b2"])],
            )
        ],
        blocks=[
            Block(id="b1", kind="heading", text="Coberturas", page=3, bbox=(72, 90, 300, 110), page_size=(595, 842)),
            Block(id="b2", kind="table", text="| Bem | Limite |\n| Casa | 100 mil |", page=4),
        ],
        passages=[Passage(id="p1", section_id="s2", text="Casa: 100 mil", page=4, end_page=4, block_ids=["b2"])],
        stats=DocStats(pages=12, words=3400, tables=1, figures=0),
        note=None,
    )

    assert DocIndex.model_validate_json(index.model_dump_json()) == index
