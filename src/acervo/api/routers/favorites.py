from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from acervo.api.deps import get_uow, require_api_key
from acervo.schemas.common import ErrorResponse
from acervo.schemas.favorite import FavoritePlace
from acervo.schemas.node import NodeRead, NodeWithPath
from acervo.services.favorite_service import FavoriteService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1",
    tags=["favorites"],
    dependencies=[Depends(require_api_key)],
    responses={401: ERROR, 422: ERROR},
)


# Typed loosely: only api/deps.py may import the UnitOfWork (tests/unit/test_layering.py).
def get_favorite_service(uow: Annotated[Any, Depends(get_uow)]) -> FavoriteService:
    return FavoriteService(uow)


Service = Annotated[FavoriteService, Depends(get_favorite_service)]


@router.get("/favorites", response_model=list[NodeWithPath])
async def list_favorites(service: Service) -> list[NodeWithPath]:
    """Live favorites of live bases, across bases, in the person's order."""
    return await service.listed()


@router.put("/nodes/{node_id}/favorite", response_model=NodeRead, responses={404: ERROR})
async def place_favorite(node_id: UUID, body: FavoritePlace, service: Service) -> NodeRead:
    """Adds a page or folder to the favorites, last or just before `before_id`; a favorite already there moves."""
    return await service.place(node_id, body)


@router.delete("/nodes/{node_id}/favorite", response_model=NodeRead, responses={404: ERROR})
async def remove_favorite(node_id: UUID, service: Service) -> NodeRead:
    return await service.remove(node_id)
