import asyncio
import hashlib
import hmac
import io
import secrets
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import BinaryIO
from uuid import UUID

from PIL import Image, ImageOps

from acervo.core.errors import CodeInvalid, ConflictError, EmailTaken, NotFoundError, ValidationError
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import (
    AccountRead,
    AccountUpdate,
    EmailCodeCreate,
    EmailCodeUpdate,
    Preferences,
    ProfileUpdate,
)
from acervo.services.mailer import Mailer, MailTemplate
from acervo.services.session_service import token_hash
from acervo.services.storage import Storage

PHOTO_SIZE = 256
CODE_LIFETIME = timedelta(minutes=10)
CODE_TRIES = 5
EMAIL_UNIQUE = "uq_account_email_lower"


def photo_key(account_id: UUID, sha256: str) -> str:
    return f"account/{account_id}/{sha256}.png"


def _square_png(data: bytes) -> bytes:
    """The centered square of a PNG, JPEG or WebP, scaled to `PHOTO_SIZE`, as PNG."""
    try:
        with Image.open(io.BytesIO(data), formats=["PNG", "JPEG", "WEBP"]) as image:
            # Phones store JPEGs sideways and say so in EXIF; without this the photo shows rotated.
            square = ImageOps.fit(ImageOps.exif_transpose(image), (PHOTO_SIZE, PHOTO_SIZE))
            # A CMYK JPEG has no PNG form.
            square = square.convert("RGBA")
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("a foto deve ser uma imagem PNG, JPEG ou WebP", {}) from exc
    out = io.BytesIO()
    square.save(out, "PNG")
    return out.getvalue()


def _now() -> datetime:
    return datetime.now(UTC)


class AccountService:
    """The signed-in person's own account: name, photo, email and preferences."""

    def __init__(
        self,
        uow: UnitOfWork,
        storage: Storage,
        mailer: Mailer,
        photo_max_bytes: int,
        now: Callable[[], datetime] = _now,
    ) -> None:
        self._uow = uow
        self._storage = storage
        self._mailer = mailer
        self._photo_max_bytes = photo_max_bytes
        self._now = now

    async def get(self, account_id: UUID) -> AccountRead:
        return AccountRead.of(await self._uow.accounts.get(account_id))

    async def rename(self, account_id: UUID, data: ProfileUpdate) -> AccountRead:
        name = data.name.strip()
        if not name:
            raise ValidationError("a conta precisa de um nome", {"name": data.name})
        return await self._update(account_id, AccountUpdate(name=name))

    async def set_preferences(self, account_id: UUID, preferences: Preferences) -> AccountRead:
        return await self._update(account_id, AccountUpdate(**preferences.model_dump()))

    async def set_photo(self, account_id: UUID, source: BinaryIO) -> AccountRead:
        """Keeps the centered square of the image as the photo; the previous one leaves the bucket."""
        source.seek(0)
        data = source.read(self._photo_max_bytes + 1)
        if len(data) > self._photo_max_bytes:
            limit = self._photo_max_bytes // (1024 * 1024)
            raise ValidationError(f"a foto passa de {limit} MB", {"max_bytes": self._photo_max_bytes})
        png = await asyncio.to_thread(_square_png, data)
        key = photo_key(account_id, hashlib.sha256(png).hexdigest())
        await self._storage.put(key, io.BytesIO(png), len(png))
        return await self._replace_photo(account_id, key)

    async def remove_photo(self, account_id: UUID) -> AccountRead:
        return await self._replace_photo(account_id, None)

    async def open_photo(self, account_id: UUID) -> tuple[str, AsyncIterator[bytes]]:
        """The photo's key, whose name is its hash, and its bytes."""
        account = await self._uow.accounts.get(account_id)
        if account.photo_key is None:
            raise NotFoundError(f"photo of {account_id} not found", {"id": str(account_id)})
        # The bytes come from the bucket; the database is not held while they are sent.
        await self._uow.rollback()
        return account.photo_key, self._storage.stream(account.photo_key)

    async def request_email_change(self, account_id: UUID, new_email: str) -> None:
        """Sends a code to `new_email`; the email changes only once the code comes back."""
        if await self._uow.accounts.by_email(new_email) is not None:
            raise EmailTaken("email already in use", {"email": new_email})
        account = await self._uow.accounts.get(account_id)
        live = await self._uow.email_codes.live(account_id, "change_email")
        if live is not None:
            await self._uow.email_codes.update(live.id, EmailCodeUpdate(used_at=self._now()))
        code = f"{secrets.randbelow(10**6):06d}"
        await self._uow.email_codes.create(
            EmailCodeCreate(
                account_id=account_id,
                purpose="change_email",
                target_email=new_email,
                code_hash=token_hash(code),
                expires_at=self._now() + CODE_LIFETIME,
            )
        )
        await self._uow.commit()
        await self._mailer.send(
            new_email, MailTemplate.CHANGE_EMAIL_CODE, account.language, {"code": code, "name": account.name}
        )

    async def confirm_email_change(self, account_id: UUID, code: str) -> AccountRead:
        """Moves the account to the code's address and tells the old address."""
        live = await self._uow.email_codes.live(account_id, "change_email")
        if live is None or live.expires_at <= self._now() or live.attempts >= CODE_TRIES:
            raise CodeInvalid("wrong, expired or used code", {})
        if not hmac.compare_digest(live.code_hash, token_hash(code)):
            await self._uow.email_codes.update(live.id, EmailCodeUpdate(attempts=live.attempts + 1))
            await self._uow.commit()
            raise CodeInvalid("wrong, expired or used code", {})
        old = await self._uow.accounts.get(account_id)
        await self._uow.email_codes.update(live.id, EmailCodeUpdate(used_at=self._now()))
        try:
            change = AccountUpdate(email=live.target_email, email_verified_at=self._now())
            account = await self._uow.accounts.update(account_id, change)
        except ConflictError as exc:
            if exc.details.get("constraint") != EMAIL_UNIQUE:
                raise
            raise EmailTaken("email already in use", {"email": live.target_email}) from exc
        await self._uow.commit()
        values = {"name": account.name, "new_email": account.email}
        await self._mailer.send(old.email, MailTemplate.EMAIL_CHANGED, account.language, values)
        return AccountRead.of(account)

    async def _update(self, account_id: UUID, change: AccountUpdate) -> AccountRead:
        account = await self._uow.accounts.update(account_id, change)
        await self._uow.commit()
        return AccountRead.of(account)

    async def _replace_photo(self, account_id: UUID, key: str | None) -> AccountRead:
        old = (await self._uow.accounts.get(account_id)).photo_key
        account = await self._update(account_id, AccountUpdate(photo_key=key))
        # Only after the commit, so the account never points at a deleted photo.
        if old is not None and old != key:
            await self._storage.delete(old)
        return account
