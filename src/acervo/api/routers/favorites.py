from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from acervo.api.deps import SIGNED_IN, CurrentAccount, get_favorite_service
from acervo.schemas.common import ErrorResponse
from acervo.schemas.favorite import FavoritePlace
from acervo.schemas.node import NodeRead, NodeWithPath
from acervo.services.favorite_service import FavoriteService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1",
    tags=["favorites"],
    dependencies=SIGNED_IN,
    responses={401: ERROR, 422: ERROR},
)


Service = Annotated[FavoriteService, Depends(get_favorite_service)]


@router.get("/favorites", response_model=list[NodeWithPath])
async def list_favorites(account: CurrentAccount, service: Service) -> list[NodeWithPath]:
    """Live favorites of live bases, across bases, in the person's order."""
    return await service.listed(account.id)


@router.put("/nodes/{node_id}/favorite", response_model=NodeRead, responses={404: ERROR})
async def place_favorite(node_id: UUID, body: FavoritePlace, account: CurrentAccount, service: Service) -> NodeRead:
    """Adds a page or folder to the favorites, last or just before `before_id`; a favorite already there moves."""
    return await service.place(account.id, node_id, body)


@router.delete("/nodes/{node_id}/favorite", response_model=NodeRead, responses={404: ERROR})
async def remove_favorite(node_id: UUID, account: CurrentAccount, service: Service) -> NodeRead:
    return await service.remove(account.id, node_id)
