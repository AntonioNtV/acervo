from functools import lru_cache

from pydantic import SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration read from the environment and `.env`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Signs the links and short-lived cookies the API hands out.
    session_secret: SecretStr
    # Where the web app is served: links in emails point there, and the session cookie is Secure under https.
    public_url: str = "http://localhost:5173"
    # No host: emails are not sent.
    smtp_host: str | None = None
    smtp_port: int = 1025
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_tls: bool = False
    mail_from: str = "Acervo <acervo@localhost>"
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    # A session ends this long after its last request.
    session_days: int = 30
    photo_max_bytes: int = 2 * 1024 * 1024
    database_url: str = "postgresql+asyncpg://acervo:acervo@localhost:55433/acervo"
    s3_endpoint: str = "http://localhost:59000"
    s3_access_key: str = "acervo"
    s3_secret_key: str = "acervo-secret"
    s3_bucket: str = "acervo"
    cors_origins: list[str] = ["http://localhost:5173"]
    # A save after this long without a change to the working text starts a new editing session, cutting a version.
    version_idle_seconds: int = 300
    cover_max_bytes: int = 10 * 1024 * 1024
    attachment_max_bytes: int = 100 * 1024 * 1024
    link_preview_timeout_seconds: float = 5
    link_preview_max_bytes: int = 1024 * 1024

    @field_validator("session_secret")
    @classmethod
    def _secret_is_set(cls, value: SecretStr, info: ValidationInfo) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError(f"{(info.field_name or '').upper()} cannot be empty")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
