from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Body, Depends

from acervo.api.deps import get_conversation_service, get_job_queue, get_proposal_service, get_settings, require_api_key
from acervo.core.settings import Settings
from acervo.schemas.common import ErrorResponse
from acervo.schemas.conversation import MessageRead
from acervo.schemas.proposal import AcceptedBy, ProposalPayload, ProposalRead, ProposalReject, ProposalSummary
from acervo.services.conversation_service import ConversationService
from acervo.services.events import JobQueue
from acervo.services.proposal_service import ProposalService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1",
    tags=["proposals"],
    dependencies=[Depends(require_api_key)],
    responses={401: ERROR, 422: ERROR},
)

Service = Annotated[ProposalService, Depends(get_proposal_service)]


@router.get("/kbs/{kb_id}/proposals", response_model=list[ProposalSummary], responses={404: ERROR})
async def list_proposals(
    kb_id: UUID,
    service: Service,
    settings: Annotated[Settings, Depends(get_settings)],
    status: Literal["pending", "applied"] = "pending",
    accepted_by: AcceptedBy | None = None,
) -> list[ProposalSummary]:
    """The base's proposals waiting for the person, from any conversation or agent, newest first; with
    `status=applied`, those applied in the last days, most recent first (`accepted_by=auto`: by an agent in auto
    mode), each with its agent's name, to undo."""
    since = None
    if status == "applied":
        since = datetime.now(UTC) - timedelta(days=settings.applied_list_days)
    return await service.listed(kb_id, status, accepted_by, since)


@router.get("/proposals/{proposal_id}", response_model=ProposalRead, responses={404: ERROR})
async def get_proposal(proposal_id: UUID, service: Service) -> ProposalRead:
    return await service.get(proposal_id)


@router.post("/proposals/{proposal_id}/accept", response_model=ProposalRead, responses={404: ERROR, 409: ERROR})
async def accept_proposal(
    proposal_id: UUID, service: Service, jobs: Annotated[JobQueue, Depends(get_job_queue)]
) -> ProposalRead:
    """Applies it, its edited version if any; accepting an applied one changes nothing. When its section or line is
    gone it comes back `stale` and nothing changes."""
    proposal = await service.accept(proposal_id)
    await service.enqueue_refresh(jobs, proposal)
    return proposal


@router.post("/proposals/{proposal_id}/reject", response_model=ProposalRead, responses={404: ERROR, 409: ERROR})
async def reject_proposal(proposal_id: UUID, body: ProposalReject, service: Service) -> ProposalRead:
    return await service.reject(proposal_id, body.reason)


@router.patch("/proposals/{proposal_id}", response_model=ProposalRead, responses={404: ERROR, 409: ERROR})
async def edit_proposal(proposal_id: UUID, body: Annotated[ProposalPayload, Body()], service: Service) -> ProposalRead:
    """The person's version of what it does, of the same kind; the original is kept."""
    return await service.edit(proposal_id, body)


@router.post("/proposals/{proposal_id}/other-place", response_model=ProposalRead, responses={404: ERROR, 409: ERROR})
async def other_place(proposal_id: UUID, service: Service) -> ProposalRead:
    """A new page or a file goes to the second place that was close instead."""
    return await service.other_place(proposal_id)


@router.post(
    "/proposals/{proposal_id}/undo", status_code=201, response_model=ProposalRead, responses={404: ERROR, 409: ERROR}
)
async def undo_proposal(
    proposal_id: UUID, service: Service, jobs: Annotated[JobQueue, Depends(get_job_queue)]
) -> ProposalRead:
    """A new proposal undoing an applied one, by the same agent and in its mode: applied at once in auto mode."""
    undo = await service.undo(proposal_id)
    await service.enqueue_refresh(jobs, undo)
    return undo


@router.post(
    "/proposals/{proposal_id}/redo", status_code=201, response_model=MessageRead, responses={404: ERROR, 409: ERROR}
)
async def redo_proposal(
    proposal_id: UUID, conversations: Annotated[ConversationService, Depends(get_conversation_service)]
) -> MessageRead:
    """A stale proposal's message run again into a new reply, whose events arrive on the conversation's stream;
    the stale one becomes rejected with no reason. Only a stale proposal of a chat message: 409 otherwise."""
    return await conversations.redo(proposal_id)
