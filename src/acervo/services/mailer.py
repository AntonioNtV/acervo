from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from acervo.schemas.account import Language
from acervo.schemas.notification import Notification


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
    LOGIN_CODE = "login_code"
    NEW_SIGN_IN = "new_sign_in"
    SECURITY_CHANGE = "security_change"
    LOCKOUT = "lockout"
    ORG_REQUIRES_2FA = "org_requires_2fa"
    DIGEST = "digest"
    ACCOUNT_DELETED = "account_deleted"
    ORG_DELETED = "org_deleted"


@dataclass(frozen=True)
class Unsubscribe:
    """Who gets the email and the toggle its "Parar de receber" link turns off."""

    account_id: UUID
    notification: Notification


class Mailer(Protocol):
    async def send(
        self,
        to: str,
        template: MailTemplate,
        language: Language,
        values: Mapping[str, str],
        *,
        unsubscribe: Unsubscribe | None = None,
    ) -> None:
        """Sends `template` in `language` to `to`, filled with `values`: `code`, `link`, `name`, `new_email`;
        for the organization emails also `inviter`, `actor`, `organization`, `base`, `member_email`, `role` and
        `old_role` (role codes), `bases` (base names, one per line) and `expires_at` (ISO 8601); for the security
        emails `browser` and `system` (from the user agent, empty when unknown), `method` (`new_sign_in`: password,
        google, passkey or reset), `change` (`security_change`: a key of `mail_templates.CHANGES`) and `passkey`
        (its name, for a passkey change); for `digest` `count` and `pages` (one page per line,
        `title\tauthors\tbase`, authors already joined); for `account_deleted` `bases` and for `org_deleted`
        `actor`, `organization` and `bases` (a count of bases, for these two). `link` is the token for `reset_link`
        and `org_invite`, and the app path for the other emails with a button but `digest`. With `unsubscribe`, the
        footer and the List-Unsubscribe headers carry a signed link that turns its toggle off."""
        ...


@dataclass(frozen=True)
class SentMail:
    to: str
    template: MailTemplate
    language: Language
    values: Mapping[str, str]
    unsubscribe: Unsubscribe | None = None


@dataclass
class FakeMailer:
    """Keeps what it would send, for the tests and for running without SMTP."""

    sent: list[SentMail] = field(default_factory=list)

    async def send(
        self,
        to: str,
        template: MailTemplate,
        language: Language,
        values: Mapping[str, str],
        *,
        unsubscribe: Unsubscribe | None = None,
    ) -> None:
        # Rendered like the real mailer does, so a value the template needs and the caller forgot fails here too.
        from acervo.services.mail_templates import render

        link = "http://acervo.test/descadastro/token" if unsubscribe else None
        render(template, language, to, values, "http://acervo.test", datetime.now(UTC), link)
        self.sent.append(SentMail(to, template, language, dict(values), unsubscribe))
