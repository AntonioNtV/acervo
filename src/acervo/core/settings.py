from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Thresholds(BaseModel):
    """Every cut-off a probability from Jev is compared to (skill `jev-decisions`)."""

    # Below, for the most likely understanding of a message: ask the person first, nothing runs before the choice.
    route_min: float = 0.60
    # Above, for "the message is about two things": split it and handle each part in the same reply.
    route_split: float = 0.70
    # Below: do not choose a place; ask the person with the top 3 options.
    place_min: float = 0.60
    # Below: the proposal shows the 2nd option next to the 1st.
    place_show_second: float = 0.90
    # Above: "already written", no proposal.
    covered: float = 0.80
    # Above: a conflict proposal instead of an edit.
    contradicts: float = 0.60
    # Above, for the page line about the same thing as the input: edit that line instead of appending a new one.
    same_line: float = 0.70
    # Below, for the most likely kind of an organizar (move, rename, undo): ask the person which, propose nothing.
    organize_min: float = 0.60
    # Above: propose replacing the existing PDF with the new one.
    pdf_new_version: float = 0.70
    # Above: the read page is kept as evidence.
    page_answers: float = 0.50
    # Above: stop navigating and answer.
    sufficient: float = 0.80
    # Below: the claim is removed from the answer.
    claim_supported: float = 0.70


class NavigatorBudget(BaseModel):
    """What one question may spend before the Navigator says "Não encontrei" (skill `navigator-agent`)."""

    expansion_rounds: int = 3
    pages_read: int = 25
    jev_questions: int = 30


class LlmRoles(BaseModel):
    """The model serving each role, as a PydanticAI model string `<provider>:<model>` (skill `llm-calls`)."""

    card: str = "anthropic:claude-haiku-5-5"
    patch: str = "anthropic:claude-opus-5-5"
    split_message: str = "anthropic:claude-haiku-5-5"
    describe: str = "anthropic:claude-haiku-5-5"
    explain: str = "anthropic:claude-haiku-5-5"
    # The LLM decider, until Jev's client exists: probabilities per option through structured output.
    decide: str = "anthropic:claude-opus-5-5"


class Settings(BaseSettings):
    """Configuration read from the environment and `.env`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: SecretStr
    database_url: str = "postgresql+asyncpg://acervo:acervo@localhost:55433/acervo"
    redis_url: str = "redis://localhost:56379/0"
    s3_endpoint: str = "http://localhost:59000"
    s3_access_key: str = "acervo"
    s3_secret_key: str = "acervo-secret"
    s3_bucket: str = "acervo"
    cors_origins: list[str] = ["http://localhost:5173"]
    thresholds: Thresholds = Thresholds()
    navigator_budget: NavigatorBudget = NavigatorBudget()
    llm_roles: LlmRoles = LlmRoles()
    # Who answers decisions: Jev (refused as not configured until its client exists), the LLM, or the tests' fake.
    decider: Literal["jev", "llm", "fake"] = "llm"
    # A save after this long without a change to the working text starts a new editing session, cutting a version.
    version_idle_seconds: int = 300
    cover_max_bytes: int = 10 * 1024 * 1024
    # A message's job is cancelled past this, and its reply marked failed.
    job_timeout_seconds: int = 600
    # The list of applied proposals, where an agent's automatic changes are undone, goes back this many days.
    applied_list_days: int = 7

    @field_validator("api_key")
    @classmethod
    def _api_key_is_set(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError("API_KEY cannot be empty")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
