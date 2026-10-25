from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration read from the environment and `.env`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: SecretStr
    database_url: str = "postgresql+asyncpg://acervo:acervo@localhost:55433/acervo"
    s3_endpoint: str = "http://localhost:59000"
    s3_access_key: str = "acervo"
    s3_secret_key: str = "acervo-secret"
    s3_bucket: str = "acervo"
    cors_origins: list[str] = ["http://localhost:5173"]
    # A save after this long without a change to the working text starts a new editing session, cutting a version.
    version_idle_seconds: int = 300
    cover_max_bytes: int = 10 * 1024 * 1024

    @field_validator("api_key")
    @classmethod
    def _api_key_is_set(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError("API_KEY cannot be empty")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
