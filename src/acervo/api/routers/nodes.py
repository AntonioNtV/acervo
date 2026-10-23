from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from acervo.api.deps import get_duplicate_service, get_tree_service, require_api_key
from acervo.schemas.common import ErrorResponse
from acervo.schemas.node import NodeAdd, NodeEdit, NodeMove, NodeRead, NodeWithPath, RestoredNode, TreeNode
from acervo.schemas.page import NodeDetail
from acervo.services.duplicate_service import DuplicateService
from acervo.services.tree_service import TreeService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1",
    tags=["nodes"],
    dependencies=[Depends(require_api_key)],
    responses={401: ERROR, 422: ERROR},
)


Service = Annotated[TreeService, Depends(get_tree_service)]


@router.get("/kbs/{kb_id}/children", response_model=list[TreeNode], responses={404: ERROR})
async def list_children(kb_id: UUID, service: Service, parent_id: UUID | None = None) -> list[TreeNode]:
    """Live children of a folder, or of the base's root when `parent_id` is left out, in the person's order."""
    return await service.children(kb_id, parent_id)


@router.get("/kbs/{kb_id}/search", response_model=list[NodeWithPath])
async def search_nodes(kb_id: UUID, q: str, service: Service) -> list[NodeWithPath]:
    """Live nodes whose title contains `q`, ignoring case and accents, closest first."""
    return await service.search(kb_id, q)


@router.post("/kbs/{kb_id}/nodes", status_code=201, response_model=NodeRead, responses={404: ERROR, 409: ERROR})
async def create_node(kb_id: UUID, body: NodeAdd, service: Service) -> NodeRead:
    """A new folder, or a page with an empty first version."""
    return await service.create(kb_id, body)


@router.get("/nodes/{node_id}", response_model=NodeDetail, responses={404: ERROR})
async def get_node(node_id: UUID, service: Service) -> NodeDetail:
    """The live node with its path, and a page's text or a file's current content."""
    return await service.detail(node_id)


@router.patch("/nodes/{node_id}", response_model=NodeRead, responses={404: ERROR, 409: ERROR})
async def edit_node(node_id: UUID, body: NodeEdit, service: Service) -> NodeRead:
    """Renaming a page also fixes the `[[…]]` links that resolved to it; a description the person edits is locked."""
    return await service.edit(node_id, body)


@router.post("/nodes/{node_id}/move", response_model=NodeRead, responses={404: ERROR, 409: ERROR})
async def move_node(node_id: UUID, body: NodeMove, service: Service) -> NodeRead:
    return await service.move(node_id, body)


@router.delete("/nodes/{node_id}", response_model=NodeRead, responses={404: ERROR})
async def trash_node(node_id: UUID, service: Service) -> NodeRead:
    """Moves the node and everything under it to its base's trash."""
    return await service.trash(node_id)


@router.post("/nodes/{node_id}/restore", response_model=RestoredNode, responses={404: ERROR, 409: ERROR})
async def restore_node(node_id: UUID, service: Service) -> RestoredNode:
    return await service.restore(node_id)


@router.post("/nodes/{node_id}/duplicate", status_code=201, response_model=NodeRead, responses={404: ERROR})
async def duplicate_node(
    node_id: UUID, service: Annotated[DuplicateService, Depends(get_duplicate_service)]
) -> NodeRead:
    """A copy of the page, "<título> (cópia)" right after it, with its text and its sub-pages; files are not copied."""
    return await service.duplicate(node_id)
