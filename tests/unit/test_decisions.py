import pytest
from pydantic import ValidationError

from acervo.domain.decisions import Answers, Choice, Noul

PLACE = Choice(id="place", question="Onde guardar?", options=("Bradesco", "Itaú", "Porto"))
COVERED = Noul(id="covered", question="Já está escrito na página?")


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
