import hmac
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from acervo.core.errors import CodeInvalid, TooManyAttempts, ValidationError
from acervo.domain.user_agent import device
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead, AccountRecord, AccountUpdate, EmailCodeCreate, EmailCodeUpdate
from acervo.schemas.security import SecurityEventKind, TwoFactorMethod, TwoFactorStart
from acervo.services.auth_service import CODE_TRIES, CODE_TTL, RESEND_AFTER
from acervo.services.mailer import Mailer, MailTemplate
from acervo.services.security_log import SecurityLog
from acervo.services.session_service import token_hash
from acervo.services.whatsapp import WhatsAppSender

SECURITY_PATH = "/conta/seguranca"


def _now() -> datetime:
    return datetime.now(UTC)


class TwoFactorService:
    """Turns two-step verification on and off for the signed-in account: one method at a time, email or WhatsApp."""

    def __init__(
        self,
        uow: UnitOfWork,
        mailer: Mailer,
        whatsapp: WhatsAppSender,
        whatsapp_language: str,
        now: Callable[[], datetime] = _now,
    ) -> None:
        self._uow = uow
        self._mailer = mailer
        self._whatsapp = whatsapp
        self._whatsapp_language = whatsapp_language
        self._now = now

    async def start(self, account_id: UUID, data: TwoFactorStart, user_agent: str | None) -> AccountRead:
        """Email is on at once, the account's email being confirmed already; WhatsApp gets a code on `data.phone`
        and is on only once `confirm` takes it back."""
        now = self._now()
        account = await self._uow.accounts.get(account_id)
        if data.method == "email":
            return await self._turn(account, "email", None, user_agent)
        if data.phone is None:
            raise ValidationError("WhatsApp needs the phone number", {"phone": None})
        live = await self._uow.email_codes.live(account_id, "two_factor")
        if live is not None and now - live.created_at < RESEND_AFTER:
            raise TooManyAttempts("a code was sent less than a minute ago")
        if live is not None:
            await self._uow.email_codes.update(live.id, EmailCodeUpdate(used_at=now))
        code = f"{secrets.randbelow(1_000_000):06d}"
        await self._uow.email_codes.create(
            EmailCodeCreate(
                account_id=account_id,
                purpose="two_factor",
                target_email=data.phone,
                code_hash=token_hash(code),
                expires_at=now + CODE_TTL,
            ),
            created_at=now,
        )
        await self._uow.commit()
        await self._whatsapp.send_code(data.phone, code, self._whatsapp_language)
        return AccountRead.of(account)

    async def confirm(self, account_id: UUID, code: str, user_agent: str | None) -> AccountRead:
        """The code sent by WhatsApp confirms the number and turns WhatsApp on in place of any other method."""
        now = self._now()
        live = await self._uow.email_codes.live(account_id, "two_factor")
        if live is None or live.expires_at <= now or live.attempts >= CODE_TRIES:
            raise CodeInvalid("wrong, expired or used code")
        if not hmac.compare_digest(live.code_hash, token_hash(code)):
            await self._uow.email_codes.update(live.id, EmailCodeUpdate(attempts=live.attempts + 1))
            await self._uow.commit()
            raise CodeInvalid("wrong, expired or used code")
        await self._uow.email_codes.update(live.id, EmailCodeUpdate(used_at=now))
        account = await self._uow.accounts.get(account_id)
        return await self._turn(account, "whatsapp", live.target_email, user_agent)

    async def disable(self, account_id: UUID, user_agent: str | None) -> AccountRead:
        account = await self._uow.accounts.get(account_id)
        if account.two_factor == "none":
            return AccountRead.of(account)
        updated = await self._uow.accounts.update(account_id, AccountUpdate(two_factor="none"))
        await self._tell(updated, SecurityEventKind.TWO_FACTOR_OFF, account.two_factor, user_agent)
        return AccountRead.of(updated)

    async def _turn(
        self, account: AccountRecord, method: TwoFactorMethod, phone: str | None, user_agent: str | None
    ) -> AccountRead:
        if account.two_factor == method and phone is None:
            return AccountRead.of(account)
        change = AccountUpdate(two_factor=method)
        if phone is not None:
            change.phone, change.phone_verified_at = phone, self._now()
        updated = await self._uow.accounts.update(account.id, change)
        await self._tell(updated, SecurityEventKind.TWO_FACTOR_ON, method, user_agent)
        return AccountRead.of(updated)

    async def _tell(self, account: AccountRecord, kind: SecurityEventKind, method: str, user_agent: str | None) -> None:
        """Logs the change and, once it is kept, emails `security_change` to the account."""
        await SecurityLog(self._uow).record(kind, account_id=account.id, data={"method": method}, user_agent=user_agent)
        await self._uow.commit()
        browser, system = device(user_agent)
        values = {
            "name": account.name,
            "change": kind.value,
            "link": SECURITY_PATH,
            "browser": browser or "",
            "system": system or "",
        }
        await self._mailer.send(account.email, MailTemplate.SECURITY_CHANGE, account.language, values)
