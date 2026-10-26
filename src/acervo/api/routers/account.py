from pathlib import PurePosixPath
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import StreamingResponse

from acervo.api.deps import CurrentAccount, current_account, get_account_service
from acervo.schemas.account import AccountRead, CodeIn, EmailChange, Preferences, ProfileUpdate
from acervo.schemas.common import ErrorResponse
from acervo.services.account_service import AccountService

ERROR: dict[str, Any] = {"model": ErrorResponse}

# `/v1`, not `/v1/account`: the photo of any account is served at `/v1/accounts/{id}/photo`.
router = APIRouter(prefix="/v1", tags=["account"], responses={401: ERROR, 422: ERROR})


Service = Annotated[AccountService, Depends(get_account_service)]


@router.get("/account", response_model=AccountRead)
async def get_account(account: CurrentAccount, service: Service) -> AccountRead:
    return await service.get(account.id)


@router.patch("/account", response_model=AccountRead)
async def rename_account(body: ProfileUpdate, account: CurrentAccount, service: Service) -> AccountRead:
    return await service.rename(account.id, body)


@router.put("/account/preferences", response_model=AccountRead)
async def set_preferences(body: Preferences, account: CurrentAccount, service: Service) -> AccountRead:
    """Replaces every preference at once."""
    return await service.set_preferences(account.id, body)


@router.put("/account/photo", response_model=AccountRead)
async def set_photo(file: UploadFile, account: CurrentAccount, service: Service) -> AccountRead:
    """A PNG, JPEG or WebP of at most 2 MB; its centered square, 256 px, becomes the photo."""
    return await service.set_photo(account.id, file.file)


@router.delete("/account/photo", response_model=AccountRead)
async def remove_photo(account: CurrentAccount, service: Service) -> AccountRead:
    """Back to the initials."""
    return await service.remove_photo(account.id)


@router.post("/account/email", status_code=204, responses={409: ERROR})
async def request_email_change(body: EmailChange, account: CurrentAccount, service: Service) -> None:
    """Sends a code to the new address; the email changes only on `POST /v1/account/email/confirm`."""
    await service.request_email_change(account.id, body.new_email)


@router.post("/account/email/confirm", response_model=AccountRead, responses={409: ERROR})
async def confirm_email_change(body: CodeIn, account: CurrentAccount, service: Service) -> AccountRead:
    """The code sent to the new address changes the email; the old address is told."""
    return await service.confirm_email_change(account.id, body.code)


@router.get(
    "/accounts/{account_id}/photo",
    response_class=StreamingResponse,
    dependencies=[Depends(current_account)],
    responses={200: {"content": {"image/png": {}}, "description": "The photo, a 256 px square."}, 404: ERROR},
)
async def account_photo(account_id: UUID, service: Service) -> StreamingResponse:
    """Any account's photo, for any signed-in person."""
    key, body = await service.open_photo(account_id)
    # The URL carries the photo's hash, so what one URL served never changes.
    headers = {"Cache-Control": "private, max-age=31536000, immutable", "ETag": f'"{PurePosixPath(key).stem}"'}
    return StreamingResponse(body, media_type="image/png", headers=headers)
