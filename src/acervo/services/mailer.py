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
    ORG_INVITE = "org_invite"
    INVITE_ACCEPTED = "invite_accepted"
    BASE_SHARED = "base_shared"
    ROLE_CHANGED = "role_changed"
    REMOVED = "removed"


class Mailer(Protocol):
    async def send(self, to: str, template: MailTemplate, language: Language, values: Mapping[str, str]) -> None:
        """Sends `template` in `language` to `to`, filled with `values`: `code`, `link`, `name`, `new_email`;
        for the organization emails also `inviter`, `actor`, `organization`, `base`, `member_email`, `role` and
        `old_role` (role codes), `bases` (base names, one per line) and `expires_at` (ISO 8601). `link` is the
        token for `reset_link` and `org_invite`, and the app path for the other emails with a button."""
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
