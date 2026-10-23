import hmac
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request

from acervo.core.errors import AuthError
from acervo.core.settings import Settings
from acervo.repositories.uow import UnitOfWork
from acervo.services.base_service import BaseService
from acervo.services.cover_service import CoverService
from acervo.services.duplicate_service import DuplicateService
from acervo.services.export_service import ExportService
from acervo.services.favorite_service import FavoriteService
from acervo.services.file_service import FileService
from acervo.services.page_service import PageService
from acervo.services.storage import Storage
from acervo.services.tree_service import TreeService


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_storage(request: Request) -> Storage:
    storage: Storage = request.app.state.storage
    return storage


async def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.api_key.get_secret_value().encode()
    if x_api_key is None or not hmac.compare_digest(x_api_key.encode(), expected):
        raise AuthError("Missing or invalid X-API-Key header.")


async def get_uow(request: Request) -> AsyncIterator[UnitOfWork]:
    async with UnitOfWork(request.app.state.session_factory) as uow:
        yield uow


def get_base_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> BaseService:
    return BaseService(uow)


def get_tree_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> TreeService:
    return TreeService(uow)


def get_page_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> PageService:
    return PageService(uow)


def get_file_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)], storage: Annotated[Storage, Depends(get_storage)]
) -> FileService:
    return FileService(uow, storage)


def get_favorite_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> FavoriteService:
    return FavoriteService(uow)


def get_duplicate_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> DuplicateService:
    return DuplicateService(uow)


def get_cover_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    storage: Annotated[Storage, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CoverService:
    return CoverService(uow, storage, settings.cover_max_bytes)


def get_export_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)], storage: Annotated[Storage, Depends(get_storage)]
) -> ExportService:
    return ExportService(uow, storage)
