from functools import lru_cache

from pydantic import BaseModel, SecretStr
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
