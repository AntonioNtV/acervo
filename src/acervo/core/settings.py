from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Thresholds(BaseModel):
    """Every cut-off a probability from Jev is compared to (skill `jev-decisions`)."""

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
    # Above: propose replacing the existing PDF with the new one.
    pdf_new_version: float = 0.70
    # Above: the read page is kept as evidence.
    page_answers: float = 0.50
    # Above: stop navigating and answer.
    sufficient: float = 0.80
    # Below: the claim is removed from the answer.
    claim_supported: float = 0.70
    # Below, on Jev's 0-3 usefulness score: the passage is dropped from a search's evidence.
    evidence_min: float = 1.5
    # At or above: the passage fully answers; the search stops.
    evidence_enough: float = 2.75


class RetrievalLimits(BaseModel):
    """What one search and one chat reply may spend, and how the index cuts text (skill `navigator-agent`)."""

    # Options in one Jev menu, besides "none"; more siblings are grouped.
    menu: int = 64
    # Menus sent in one Jev call.
    menus_per_call: int = 4
    # Routes kept open at each level of the descent.
    beam: int = 4
    # Nodes and sections opened before the search gives up.
    expansions: int = 96
    # Passages scored by Jev in one search.
    passages: int = 96
    # Passages scored in one Jev call.
    per_score_call: int = 16
    # Evidence returned to the LLM.
    results: int = 12
    # Characters of evidence returned to the LLM.
    result_chars: int = 24000
    # Sections of one document scored before other documents get priority.
    sections_per_document: int = 8
    # Characters of a built description Jev sees for one option.
    description_chars: int = 1200
    # Characters of one passage, and how many the next one repeats.
    passage_chars: int = 2400
    passage_overlap: int = 200
    # Steps of the chat's LLM in one reply, and how many of them may call tools.
    llm_steps: int = 6
    llm_tool_steps: int = 5
    # Partial passages kept before one Score asks whether together they answer the question.
    set_check: int = 3
    # Documents the title/heading shortcut may propose; still routed and scored by Jev.
    candidates: int = 8


class LlmRoles(BaseModel):
    """The model serving each role, as a PydanticAI model string `<provider>:<model>` (skill `llm-calls`)."""

    card: str = "anthropic:claude-haiku-5-5"
    patch: str = "anthropic:claude-opus-5-5"
    # The LLM decider: probabilities per option through structured output; DECIDER=jev uses Jev's API.
    decide: str = "anthropic:claude-opus-5-5"
    # The chat: it converses and chooses when to use the base's tools; it never decides where anything goes.
    chat: str = "anthropic:claude-sonnet-5-5"


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
    retrieval_limits: RetrievalLimits = RetrievalLimits()
    llm_roles: LlmRoles = LlmRoles()
    # Who answers decisions: Jev (refused as not configured until its client exists), the LLM, or the tests' fake.
    decider: Literal["jev", "llm", "fake"] = "llm"
    jev_api_key: SecretStr | None = None
    jev_url: str = "https://api.typesafe.ai/v1/systemone"
    jev_model: str = "jev-latest"
    # A save after this long without a change to the working text starts a new editing session, cutting a version.
    version_idle_seconds: int = 300
    cover_max_bytes: int = 10 * 1024 * 1024
    # A file sent in the chat or by an MCP agent's save_file is refused past this.
    upload_max_bytes: int = 100 * 1024 * 1024
    # A message's job is cancelled past this, and its reply marked failed.
    job_timeout_seconds: int = 600
    # How many earlier messages of a conversation the chat reads as its history.
    chat_history: int = 20
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
