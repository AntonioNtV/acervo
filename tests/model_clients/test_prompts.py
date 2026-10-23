import re

from acervo.core.settings import LlmRoles, Thresholds
from acervo.model_clients.llm_writer import PROMPTS


def test_every_role_has_a_prompt_file() -> None:
    assert {path.stem for path in PROMPTS.glob("*.md")} == set(LlmRoles.model_fields)


def test_no_prompt_contains_a_threshold_value() -> None:
    values = {value for value in Thresholds().model_dump().values()}
    for path in PROMPTS.glob("*.md"):
        numbers = {float(number.replace(",", ".")) for number in re.findall(r"\b0[.,]\d+", path.read_text())}
        percents = {int(number) / 100 for number in re.findall(r"(\d+)\s*%", path.read_text())}
        assert not (numbers | percents) & values, path.name
