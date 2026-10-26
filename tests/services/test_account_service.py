import io
import os
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import CodeInvalid, ValidationError
from acervo.core.settings import Settings
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.services.account_service import AccountService
from acervo.services.mailer import FakeMailer, MailTemplate
from acervo.services.storage import Storage

MakeAccount = Callable[..., Awaitable[AccountRead]]
RED, BLUE = (200, 0, 0), (0, 0, 200)


def _encode(image: Image.Image, format: str, **options: object) -> io.BytesIO:
    out = io.BytesIO()
    image.save(out, format, **options)
    return out


@pytest.fixture
async def service(
    uow: UnitOfWork, session: AsyncSession, storage: Settings, fake_mailer: FakeMailer
) -> AsyncIterator[AccountService]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield AccountService(uow, Storage(storage), fake_mailer, storage.photo_max_bytes)


async def test_photo_is_the_centered_square_at_256_px(service: AccountService, make_account: MakeAccount) -> None:
    ana = await make_account()
    wide = Image.new("RGB", (900, 300), BLUE)
    wide.paste(Image.new("RGB", (300, 300), RED), (300, 0))

    account = await service.set_photo(ana.id, _encode(wide, "PNG"))
    _, body = await service.open_photo(ana.id)
    photo = Image.open(io.BytesIO(b"".join([chunk async for chunk in body])))

    assert account.photo_url is not None
    assert (photo.format, photo.size) == ("PNG", (256, 256))
    # Resampling blends a little of the blue sides into the edges.
    assert all(photo.getpixel(corner)[0] > 150 for corner in [(0, 0), (255, 0), (0, 255), (255, 255)])


async def test_a_1_mb_jpeg_is_taken_and_a_3_mb_image_refused(
    service: AccountService, make_account: MakeAccount
) -> None:
    ana = await make_account()
    noise = Image.frombytes("RGB", (1000, 800), os.urandom(1000 * 800 * 3))
    jpeg = _encode(noise, "JPEG", quality=95)
    too_big = io.BytesIO(jpeg.getvalue() + bytes(3 * 1024 * 1024 - jpeg.tell()))

    taken = await service.set_photo(ana.id, jpeg)
    with pytest.raises(ValidationError):
        await service.set_photo(ana.id, too_big)

    assert 1024 * 1024 * 0.8 < len(jpeg.getvalue()) < 2 * 1024 * 1024
    assert (await service.get(ana.id)).photo_url == taken.photo_url


async def test_email_changes_only_after_the_code_and_the_old_address_is_told(
    service: AccountService, make_account: MakeAccount, fake_mailer: FakeMailer
) -> None:
    ana = await make_account(email="ana@example.com")

    await service.request_email_change(ana.id, "ana@novo.com")
    sent = fake_mailer.sent[-1]
    wrong = f"{(int(sent.values['code']) + 1) % 10**6:06d}"
    with pytest.raises(CodeInvalid):
        await service.confirm_email_change(ana.id, wrong)
    unchanged = await service.get(ana.id)
    changed = await service.confirm_email_change(ana.id, sent.values["code"])

    assert (sent.to, sent.template) == ("ana@novo.com", MailTemplate.CHANGE_EMAIL_CODE)
    assert unchanged.email == "ana@example.com"
    assert changed.email == "ana@novo.com"
    notice = fake_mailer.sent[-1]
    assert (notice.to, notice.template, notice.values["new_email"]) == (
        "ana@example.com",
        MailTemplate.EMAIL_CHANGED,
        "ana@novo.com",
    )
