import base64
import json
import secrets
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import parse_authentication_credential_json, parse_registration_credential_json
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from acervo.core import signing
from acervo.core.errors import CodeInvalid, InvalidCredentials, LastWayIn, NotFoundError
from acervo.domain.user_agent import device
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead, SessionUpdate
from acervo.schemas.security import PasskeyCreate, PasskeyRead, PasskeyRecord, PasskeyUpdate, SecurityEventKind
from acervo.services.mailer import Mailer, MailTemplate
from acervo.services.security_log import SecurityLog
from acervo.services.session_service import SessionService, token_hash

CHALLENGE_SECONDS = 5 * 60
RP_NAME = "Acervo"
DEFAULT_NAME = "Passkey"
# The authenticators the spec names, by the AAGUID they report (passkeydeveloper/passkey-authenticator-aaguids).
KNOWN_AUTHENTICATORS = {
    "fbfc3007-154e-4ecc-8c0b-6e020557d7bd": "iCloud Keychain",
    "ea9b8d66-4d01-1d21-3ce4-b6b48cb575d4": "Google Password Manager",
    "adce0002-35bc-c60a-648b-0b25f1f05503": "Chrome on Mac",
    "bada5566-a7aa-401f-bd96-45619a55120d": "1Password",
    "d548826e-79b4-db40-a3d8-11116f7e8349": "Bitwarden",
    "08987058-cadc-4b81-b6e1-30de50dcbe96": "Windows Hello",
    "9ddd1817-af5a-4672-a2b9-3e3dd95000a9": "Windows Hello",
    "6028b017-b1d4-4c02-b4b3-afcdafc96bb2": "Windows Hello",
}
SECURITY_PATH = "/conta/seguranca"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class PasskeyService:
    """Passkeys of an account (WebAuthn through py_webauthn) and signing in with them, which counts as both
    factors."""

    def __init__(
        self,
        uow: UnitOfWork,
        mailer: Mailer,
        secret: str,
        rp_id: str,
        origin: str,
        sessions: SessionService,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._uow = uow
        self._mailer = mailer
        self._secret = secret
        self._rp_id = rp_id
        self._origin = origin
        self._sessions = sessions
        self._now = now

    async def registration_options(self, account: AccountRead) -> tuple[dict[str, Any], str]:
        """The browser's creation options and the value of the short-lived cookie `register` checks."""
        challenge = secrets.token_bytes(32)
        existing = await self._uow.passkeys.of_account(account.id)
        options = generate_registration_options(
            rp_id=self._rp_id,
            rp_name=RP_NAME,
            user_id=account.id.bytes,
            user_name=account.email,
            user_display_name=account.name,
            challenge=challenge,
            exclude_credentials=[
                PublicKeyCredentialDescriptor(
                    id=passkey.credential_id, transports=[AuthenticatorTransport(t) for t in passkey.transports]
                )
                for passkey in existing
            ],
            # Discoverable, so Entrar can offer it with no email typed.
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
        )
        cookie = self._seal("passkey_register", challenge=_b64(challenge), account=str(account.id))
        return json.loads(options_to_json(options)), cookie

    async def register(
        self,
        account: AccountRead,
        credential: dict[str, Any],
        name: str | None,
        cookie: str | None,
        user_agent: str | None,
    ) -> PasskeyRead:
        """Stores the passkey the browser created for the challenge of `cookie`; logs and emails it."""
        started = self._unseal("passkey_register", cookie)
        if started is None or started["account"] != str(account.id):
            raise CodeInvalid("The passkey prompt expired; try again.")
        try:
            parsed = parse_registration_credential_json(credential)
            verified = verify_registration_response(
                credential=parsed,
                expected_challenge=_unb64(started["challenge"]),
                expected_rp_id=self._rp_id,
                expected_origin=self._origin,
            )
        except WebAuthnException as error:
            raise CodeInvalid("The passkey could not be verified.") from error
        if await self._uow.passkeys.by_credential(verified.credential_id) is not None:
            raise CodeInvalid("The passkey could not be verified.")
        passkey = await self._uow.passkeys.create(
            PasskeyCreate(
                account_id=account.id,
                credential_id=verified.credential_id,
                public_key=verified.credential_public_key,
                sign_count=verified.sign_count,
                transports=[t.value for t in parsed.response.transports or []],
                name=name or KNOWN_AUTHENTICATORS.get(verified.aaguid, DEFAULT_NAME),
                aaguid=verified.aaguid,
            )
        )
        await self._changed(account, SecurityEventKind.PASSKEY_ADDED, passkey.name, user_agent)
        return PasskeyRead.model_validate(passkey)

    async def of_account(self, account_id: UUID) -> list[PasskeyRead]:
        return [PasskeyRead.model_validate(passkey) for passkey in await self._uow.passkeys.of_account(account_id)]

    async def rename(self, account_id: UUID, passkey_id: UUID, name: str) -> PasskeyRead:
        await self._own(account_id, passkey_id)
        renamed = await self._uow.passkeys.update(passkey_id, PasskeyUpdate(name=name))
        await self._uow.commit()
        return PasskeyRead.model_validate(renamed)

    async def remove(self, account: AccountRead, passkey_id: UUID, user_agent: str | None) -> None:
        """Removes a passkey of the account, unless it is the last way to sign in; logs and emails it."""
        # Locked, so two removals at once cannot both see the other passkey left.
        passkeys = await self._uow.passkeys.of_account(account.id, lock=True)
        passkey = next((p for p in passkeys if p.id == passkey_id), None)
        if passkey is None:
            raise NotFoundError(f"passkey {passkey_id} not found", {"id": str(passkey_id)})
        if not account.has_password and not account.has_google and len(passkeys) == 1:
            raise LastWayIn("This passkey is the only way to sign in to the account.")
        await self._uow.passkeys.delete(passkey_id)
        await self._changed(account, SecurityEventKind.PASSKEY_REMOVED, passkey.name, user_agent)

    def sign_in_options(self) -> tuple[dict[str, Any], str]:
        """Request options with no allowed credentials (the browser offers the passkeys it has for the site), and
        the value of the short-lived cookie `sign_in` checks."""
        challenge = secrets.token_bytes(32)
        options = generate_authentication_options(
            rp_id=self._rp_id, challenge=challenge, user_verification=UserVerificationRequirement.PREFERRED
        )
        cookie = self._seal("passkey_sign_in", challenge=_b64(challenge), issued=str(self._now()))
        return json.loads(options_to_json(options)), cookie

    async def sign_in(
        self, credential: dict[str, Any], cookie: str | None, user_agent: str | None, current_token: str | None
    ) -> tuple[AccountRead, str]:
        """Signs in the account of the passkey; on a live session of that same account it marks it reauthenticated
        instead, keeping its token. A counter going back is refused and logged."""
        started = self._unseal("passkey_sign_in", cookie)
        if started is None:
            raise CodeInvalid("The passkey prompt expired; try again.")
        try:
            parsed = parse_authentication_credential_json(credential)
        except WebAuthnException as error:
            raise InvalidCredentials("The passkey was not accepted.") from error
        passkey = await self._uow.passkeys.by_credential(parsed.raw_id)
        user_handle = parsed.response.user_handle
        # Used since this challenge was made: the same answer sent again.
        used = None if passkey is None else passkey.last_used_at
        replayed = used is not None and used.timestamp() >= float(started["issued"])
        if passkey is None or replayed or (user_handle and user_handle != passkey.account_id.bytes):
            raise InvalidCredentials("The passkey was not accepted.")
        try:
            # The counter is checked below, so a cloned authenticator is logged rather than only refused.
            verified = verify_authentication_response(
                credential=parsed,
                expected_challenge=_unb64(started["challenge"]),
                expected_rp_id=self._rp_id,
                expected_origin=self._origin,
                credential_public_key=passkey.public_key,
                credential_current_sign_count=0,
            )
        except WebAuthnException as error:
            raise InvalidCredentials("The passkey was not accepted.") from error
        if (verified.new_sign_count or passkey.sign_count) and verified.new_sign_count <= passkey.sign_count:
            await SecurityLog(self._uow).record(
                SecurityEventKind.PASSKEY_REFUSED,
                account_id=passkey.account_id,
                data={"passkey": passkey.name},
                user_agent=user_agent,
            )
            await self._uow.commit()
            raise InvalidCredentials("The passkey was not accepted.")
        now = self._utc()
        await self._uow.passkeys.update(passkey.id, PasskeyUpdate(sign_count=verified.new_sign_count, last_used_at=now))
        token = await self._session(passkey.account_id, now, user_agent, current_token)
        await self._uow.commit()
        return AccountRead.of(await self._uow.accounts.get(passkey.account_id)), token

    async def _session(self, account_id: UUID, now: datetime, user_agent: str | None, current: str | None) -> str:
        if current is not None:
            session = await self._uow.sessions.get_by(token_hash=token_hash(current))
            if session is not None and session.account_id == account_id and session.expires_at > now:
                await self._uow.sessions.update(session.id, SessionUpdate(reauthenticated_at=now))
                return current
        return await self._sessions.create(account_id, user_agent, "passkey")

    async def _own(self, account_id: UUID, passkey_id: UUID) -> PasskeyRecord:
        passkey = await self._uow.passkeys.get_by(id=passkey_id, account_id=account_id)
        if passkey is None:
            raise NotFoundError(f"passkey {passkey_id} not found", {"id": str(passkey_id)})
        return passkey

    async def _changed(self, account: AccountRead, kind: SecurityEventKind, name: str, user_agent: str | None) -> None:
        await SecurityLog(self._uow).record(kind, account_id=account.id, data={"passkey": name}, user_agent=user_agent)
        await self._uow.commit()
        browser, system = device(user_agent)
        values = {
            "name": account.name,
            "change": kind,
            "passkey": name,
            "browser": browser or "",
            "system": system or "",
            "link": SECURITY_PATH,
        }
        await self._mailer.send(account.email, MailTemplate.SECURITY_CHANGE, account.preferences.language, values)

    def _utc(self) -> datetime:
        return datetime.fromtimestamp(self._now(), UTC)

    def _seal(self, purpose: str, **values: str) -> str:
        return signing.seal(self._secret, purpose, int(self._now()) + CHALLENGE_SECONDS, **values)

    def _unseal(self, purpose: str, sealed: str | None) -> dict[str, Any] | None:
        return signing.unseal(self._secret, purpose, sealed, self._now())
