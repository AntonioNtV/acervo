from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from acervo.domain.cards import Placement
from acervo.repositories.agent import AgentRepository
from acervo.repositories.conversation import ConversationRepository
from acervo.repositories.proposal import ProposalRepository
from acervo.schemas.agent import AgentCreate
from acervo.schemas.conversation import ConversationCreate
from acervo.schemas.proposal import (
    CreatePagePayload,
    MovePayload,
    ProposalCreate,
    ProposalUpdate,
    SavePdfPayload,
    StagedFile,
)

MakeTree = Callable[..., Awaitable[Any]]


async def test_pending_proposals_of_a_base_newest_first_with_agent_and_conversation(
    session: AsyncSession, make_tree: MakeTree
) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md"], "Arquivo": None})
    other = await make_tree({"Porto": None}, name="Jurídico")
    agents, proposals = AgentRepository(session), ProposalRepository(session)
    chat = await agents.get_by(kb_id=tree.kb.id, built_in=True)
    assert chat is not None and chat.name == "Chat do Acervo"
    claude = await agents.create(AgentCreate(name="Claude", mode="auto"), kb_id=tree.kb.id, token_hash="h")
    conversation = await ConversationRepository(session).create(
        ConversationCreate(kb_id=tree.kb.id, agent_id=chat.id, title="Prazos")
    )
    bradesco, arquivo = tree["Bradesco"], tree["Arquivo"]

    page = await proposals.create(
        ProposalCreate(
            kb_id=tree.kb.id,
            agent_id=chat.id,
            conversation_id=conversation.id,
            payload=CreatePagePayload(
                parent_id=bradesco.id, parent_path="Bradesco", title="Prazos", markdown="# Prazos\n"
            ),
            alternatives=[Placement(node_id=arquivo.id, path="Arquivo", landing="new_page", probability=0.3)],
        )
    )
    pdf = await proposals.create(
        ProposalCreate(
            kb_id=tree.kb.id,
            agent_id=claude.id,
            payload=SavePdfPayload(parent_id=bradesco.id, parent_path="Bradesco", name="CG 2026.pdf"),
            staged=StagedFile(storage_key="staged/abc", sha256="abc", size=10, name="cg.pdf"),
        )
    )
    move = MovePayload(node_id=bradesco.id, from_path="Bradesco", parent_id=arquivo.id, to_path="Arquivo")
    rejected = await proposals.create(ProposalCreate(kb_id=tree.kb.id, agent_id=chat.id, payload=move))
    await proposals.update(rejected.id, ProposalUpdate(status="rejected", reject_reason="wrong_place"))
    foreign_chat = await agents.get_by(kb_id=other.kb.id, built_in=True)
    assert foreign_chat is not None
    await proposals.create(ProposalCreate(kb_id=other.kb.id, agent_id=foreign_chat.id, payload=move))

    pending = await proposals.pending(tree.kb.id)

    assert [(p.id, p.kind, p.agent_name, p.conversation_title) for p in pending] == [
        (pdf.id, "save_pdf", "Claude", None),
        (page.id, "create_page", "Chat do Acervo", "Prazos"),
    ]
    assert pending[0].staged == pdf.staged
    assert pending[1].payload == page.payload
    assert pending[1].alternatives == page.alternatives
    assert (await proposals.get(rejected.id)).reject_reason == "wrong_place"
