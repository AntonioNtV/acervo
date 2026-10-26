import base64
import hashlib
import json
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import CodeInvalid, InvalidCredentials, LastWayIn
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead, AccountUpdate
from acervo.schemas.security import PasskeyUpdate, SecurityEventKind
from acervo.services.mailer import FakeMailer, MailTemplate
from acervo.services.passkey_service import PasskeyService
from acervo.services.session_service import SessionService

MakeAccount = Callable[..., Awaitable[AccountRead]]
RP_ID = "localhost"
ORIGIN = "http://localhost:5173"
ONE_PASSWORD = "bada5566-a7aa-401f-bd96-45619a55120d"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _challenge(options: dict[str, Any]) -> str:
    return str(options["challenge"])


class SoftAuthenticator:
    """An ES256 passkey that answers WebAuthn like a browser would, for one origin and relying party."""

    def __init__(self, origin: str = ORIGIN, rp_id: str = RP_ID, aaguid: str = ONE_PASSWORD) -> None:
        self.origin, self.rp_id = origin, rp_id
        self.aaguid = bytes.fromhex(aaguid.replace("-", ""))
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = secrets.token_bytes(16)
        self.user_handle = b""
        self.sign_count = 0
        # The UV flag: the person unlocked the authenticator (biometrics or PIN), not only touched it.
        self.user_verified = True

    def _client_data(self, kind: str, challenge: str) -> bytes:
        return json.dumps({"type": kind, "challenge": challenge, "origin": self.origin}).encode()

    def _auth_data(self, flags: int) -> bytes:
        flags |= 0x04 if self.user_verified else 0
        return hashlib.sha256(self.rp_id.encode()).digest() + bytes([flags]) + self.sign_count.to_bytes(4, "big")

    def create(self, options: dict[str, Any]) -> dict[str, Any]:
        self.user_handle = base64.urlsafe_b64decode(options["user"]["id"] + "==")
        numbers = self.key.public_key().public_numbers()
        cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")})
        attested = self.aaguid + len(self.credential_id).to_bytes(2, "big") + self.credential_id + cose
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": self._auth_data(0x41) + attested})
        return {
            "id": _b64(self.credential_id),
            "rawId": _b64(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": _b64(self._client_data("webauthn.create", _challenge(options))),
                "attestationObject": _b64(attestation),
                "transports": ["internal"],
            },
        }

    def get(self, options: dict[str, Any]) -> dict[str, Any]:
        client_data = self._client_data("webauthn.get", _challenge(options))
        auth_data = self._auth_data(0x01)
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": _b64(self.credential_id),
            "rawId": _b64(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": _b64(client_data),
                "authenticatorData": _b64(auth_data),
                "signature": _b64(signature),
                "userHandle": _b64(self.user_handle),
            },
        }


@pytest.fixture
async def service(uow: UnitOfWork, session: AsyncSession, fake_mailer: FakeMailer) -> AsyncIterator[PasskeyService]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield PasskeyService(uow, fake_mailer, "secret", RP_ID, ORIGIN, SessionService(uow, 30))


async def _kinds(uow: UnitOfWork, account_id: UUID) -> list[SecurityEventKind]:
    return [event.kind for event in await uow.security_events.of_account(account_id, datetime(2000, 1, 1, tzinfo=UTC))]


async def _register(service: PasskeyService, account: AccountRead, authenticator: SoftAuthenticator) -> None:
    options, cookie = await service.registration_options(account)
    await service.register(account, authenticator.create(options), None, cookie, "Firefox")


async def _sign_in(
    service: PasskeyService, authenticator: SoftAuthenticator, current: str | None = None
) -> tuple[AccountRead, str]:
    options, cookie = service.sign_in_options()
    return await service.sign_in(authenticator.get(options), cookie, "Firefox", current)


async def test_a_registered_passkey_signs_in_with_no_second_step(
    service: PasskeyService, uow: UnitOfWork, fake_mailer: FakeMailer, make_account: MakeAccount
) -> None:
    ana = await make_account()
    authenticator = SoftAuthenticator()

    await _register(service, ana, authenticator)
    authenticator.sign_count = 1
    account, token = await _sign_in(service, authenticator)

    assert account.id == ana.id
    assert account.has_passkey
    [passkey] = await service.of_account(ana.id)
    assert passkey.name == "1Password"
    assert passkey.last_used_at is not None
    session = await SessionService(uow, 30).resolve(token)
    assert session is not None and session.id == ana.id
    assert (await uow.sessions.of_account(ana.id))[0].method == "passkey"
    kinds = await _kinds(uow, ana.id)
    assert set(kinds) == {SecurityEventKind.PASSKEY_ADDED, SecurityEventKind.SIGNED_IN}
    [mail] = fake_mailer.sent
    assert (mail.template, mail.values["change"]) == (MailTemplate.SECURITY_CHANGE, "passkey_added")


async def test_signing_in_on_a_session_of_the_same_account_reauthenticates_it(
    service: PasskeyService, uow: UnitOfWork, make_account: MakeAccount
) -> None:
    ana = await make_account()
    authenticator = SoftAuthenticator()
    await _register(service, ana, authenticator)
    current = await SessionService(uow, 30).create(ana.id, "Firefox")

    _, token = await _sign_in(service, authenticator, current)

    assert token == current
    [session] = await uow.sessions.of_account(ana.id)
    assert session.reauthenticated_at is not None


@pytest.mark.parametrize("wrong", [{"origin": "https://evil.example"}, {"rp_id": "evil.example"}])
async def test_another_origin_or_relying_party_is_refused(
    service: PasskeyService, make_account: MakeAccount, wrong: dict[str, str]
) -> None:
    ana = await make_account()

    with pytest.raises(CodeInvalid):
        await _register(service, ana, SoftAuthenticator(**wrong))

    authenticator = SoftAuthenticator()
    await _register(service, ana, authenticator)
    for name, value in wrong.items():
        setattr(authenticator, name, value)
    with pytest.raises(InvalidCredentials):
        await _sign_in(service, authenticator)


async def test_a_replayed_challenge_is_refused(service: PasskeyService, make_account: MakeAccount) -> None:
    ana = await make_account()
    authenticator = SoftAuthenticator()
    await _register(service, ana, authenticator)
    options, cookie = service.sign_in_options()
    answer = authenticator.get(options)
    await service.sign_in(answer, cookie, "Firefox", None)

    with pytest.raises(InvalidCredentials):
        await service.sign_in(answer, cookie, "Firefox", None)
    _, other_cookie = service.sign_in_options()
    with pytest.raises(InvalidCredentials):
        await service.sign_in(answer, other_cookie, "Firefox", None)


async def test_a_counter_going_back_is_refused_and_logged(
    service: PasskeyService, uow: UnitOfWork, make_account: MakeAccount
) -> None:
    ana = await make_account()
    authenticator = SoftAuthenticator()
    await _register(service, ana, authenticator)
    [passkey] = await uow.passkeys.of_account(ana.id)
    await uow.passkeys.update(passkey.id, PasskeyUpdate(sign_count=7))
    authenticator.sign_count = 5

    with pytest.raises(InvalidCredentials):
        await _sign_in(service, authenticator)

    kinds = await _kinds(uow, ana.id)
    assert SecurityEventKind.PASSKEY_REFUSED in kinds
    assert SecurityEventKind.SIGNED_IN not in kinds


async def test_the_last_way_in_cannot_be_removed(
    service: PasskeyService, uow: UnitOfWork, fake_mailer: FakeMailer, make_account: MakeAccount
) -> None:
    ana = await make_account()
    await _register(service, ana, SoftAuthenticator())
    await _register(service, ana, SoftAuthenticator())
    await uow.accounts.update(ana.id, AccountUpdate(password_hash=None))
    ana = AccountRead.of(await uow.accounts.get(ana.id))
    first, last = await service.of_account(ana.id)

    await service.remove(ana, first.id, "Firefox")
    with pytest.raises(LastWayIn):
        await service.remove(ana, last.id, "Firefox")

    assert [passkey.id for passkey in await service.of_account(ana.id)] == [last.id]
    assert fake_mailer.sent[-1].values["change"] == "passkey_removed"


async def test_a_passkey_without_user_verification_is_refused(
    service: PasskeyService, make_account: MakeAccount
) -> None:
    ana = await make_account()
    unverified = SoftAuthenticator()
    unverified.user_verified = False
    with pytest.raises(CodeInvalid):
        await _register(service, ana, unverified)

    authenticator = SoftAuthenticator()
    await _register(service, ana, authenticator)
    authenticator.user_verified = False
    with pytest.raises(InvalidCredentials):
        await _sign_in(service, authenticator)


async def test_a_passkey_of_another_account_never_switches_a_live_session(
    service: PasskeyService, uow: UnitOfWork, make_account: MakeAccount
) -> None:
    ana, bia = await make_account(), await make_account(email="bia@example.com", name="Bia")
    authenticator = SoftAuthenticator()
    await _register(service, bia, authenticator)
    current = await SessionService(uow, 30).create(ana.id, "Firefox")

    with pytest.raises(InvalidCredentials):
        await _sign_in(service, authenticator, current)

    [session] = await uow.sessions.of_account(ana.id)
    assert session.reauthenticated_at is None
    assert await uow.sessions.of_account(bia.id) == []
