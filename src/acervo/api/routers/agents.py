from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from acervo.api.deps import get_agent_service, require_api_key
from acervo.schemas.agent import AgentConnected, AgentCreate, AgentEdit, AgentRead
from acervo.schemas.common import ErrorResponse
from acervo.services.agent_service import AgentService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1",
    tags=["agents"],
    dependencies=[Depends(require_api_key)],
    responses={401: ERROR, 404: ERROR, 422: ERROR},
)

Service = Annotated[AgentService, Depends(get_agent_service)]


@router.get("/kbs/{kb_id}/agents", response_model=list[AgentRead])
async def list_agents(kb_id: UUID, service: Service) -> list[AgentRead]:
    """The base's built-in chat first, then the agents connected to it."""
    return await service.list(kb_id)


@router.post("/kbs/{kb_id}/agents", status_code=201, response_model=AgentConnected)
async def connect_agent(kb_id: UUID, body: AgentCreate, service: Service) -> AgentConnected:
    """A new agent of the base; its token is in this response only."""
    return await service.create(kb_id, body)


@router.patch("/agents/{agent_id}", response_model=AgentRead)
async def update_agent(agent_id: UUID, body: AgentEdit, service: Service) -> AgentRead:
    return await service.update(agent_id, body)


@router.delete("/agents/{agent_id}", response_model=AgentRead, responses={409: ERROR})
async def revoke_agent(agent_id: UUID, service: Service) -> AgentRead:
    """Its token stops working at once; the agent is kept, so its proposals keep its name. The built-in chat: 409."""
    return await service.revoke(agent_id)
