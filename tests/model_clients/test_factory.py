import pytest
from pydantic import SecretStr

from acervo.core.errors import DecisionUnavailable
from acervo.core.settings import Settings
from acervo.model_clients.factory import build_decider, build_writer
from acervo.model_clients.fakes import FakeDecider, FakeWriter
from acervo.model_clients.llm_decider import LlmDecider
from acervo.model_clients.llm_writer import LlmWriter


def _with(decider: str) -> Settings:
    return Settings(api_key=SecretStr("k"), decider=decider)  # type: ignore[arg-type]


def test_the_setting_picks_the_clients() -> None:
    assert isinstance(build_decider(_with("llm")), LlmDecider)
    assert isinstance(build_writer(_with("llm")), LlmWriter)
    assert isinstance(build_decider(_with("fake")), FakeDecider)
    assert isinstance(build_writer(_with("fake")), FakeWriter)


def test_jev_without_a_key_is_refused() -> None:
    with pytest.raises(DecisionUnavailable):
        build_decider(_with("jev"))
