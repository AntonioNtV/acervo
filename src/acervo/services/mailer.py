from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from acervo.schemas.account import Language


class MailTemplate(StrEnum):
    VERIFY_CODE = "verify_code"
    RESET_LINK = "reset_link"
    CHANGE_EMAIL_CODE = "change_email_code"
    EMAIL_CHANGED = "email_changed"


class Mailer(Protocol):
    async def send(self, to: str, template: MailTemplate, language: Language, values: Mapping[str, str]) -> None:
        """Sends `template` in `language` to `to`, filled with `values` (`code`, `link`, `name`, `new_email`)."""
        ...


@dataclass(frozen=True)
class SentMail:
    to: str
    template: MailTemplate
    language: Language
    values: Mapping[str, str]


@dataclass
class FakeMailer:
    """Keeps what it would send, for the tests and for running without SMTP."""

    sent: list[SentMail] = field(default_factory=list)

    async def send(self, to: str, template: MailTemplate, language: Language, values: Mapping[str, str]) -> None:
        # Rendered like the real mailer does, so a value the template needs and the caller forgot fails here too.
        from acervo.services.mail_templates import render

        render(template, language, to, values, "http://acervo.test", datetime.now(UTC))
        self.sent.append(SentMail(to, template, language, dict(values)))
