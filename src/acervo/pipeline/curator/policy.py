"""Filing a fact or a PDF: the descent, the checks and the policy table of skill `curator-agent`."""

from uuid import UUID

from pydantic import BaseModel

from acervo.core.settings import Thresholds
from acervo.domain.cards import Card, CardInput, Placement
from acervo.model_clients.decider import Decider
from acervo.model_clients.writer import Writer
from acervo.pipeline.curator import build
from acervo.pipeline.curator.descent import Descent, Path, descend, placements
from acervo.pipeline.curator.log import Decision
from acervo.pipeline.curator.options import pdf_options, text_options
from acervo.pipeline.curator.page_check import check_page
from acervo.pipeline.curator.pdf_check import replaced_pdf
from acervo.pipeline.curator.tree import ReadPage, SnapshotNode, TreeSnapshot
from acervo.schemas.proposal import ProposalPayload

STEP = "descent"


class Propose(BaseModel):
    """A proposal to store; its payload's kind is append, edit, create_page, conflict, save_pdf or replace_pdf."""

    payload: ProposalPayload
    # The second path, when the first was not sure enough to stand alone.
    alternatives: list[Placement] | None = None


class AlreadyWritten(BaseModel):
    """Nothing to add: the reply links to the section."""

    page_id: UUID
    path: str
    anchor: str
    heading: str


class NotSure(BaseModel):
    """No place is likely enough: the person chooses among the top 3; the input waits in "Sem lugar definido"."""

    options: list[Placement]
    # For a filing, what waits there, under the likeliest place; None for an organize.
    payload: ProposalPayload | None = None


Filed = Propose | AlreadyWritten | NotSure


def card_state(card: Card) -> str:
    """The input as the decisions read it."""
    lines = [card.title, card.subject, *(f"- {fact}" for fact in card.facts)]
    if card.entities:
        lines.append(f"Menciona: {', '.join(card.entities)}")
    return "\n".join(lines)


def _likeliest(tree: TreeSnapshot, options: list[Placement]) -> SnapshotNode | None:
    first = options[0] if options else None
    return tree.node(first.node_id) if first and first.node_id else None


def place(
    tree: TreeSnapshot, descent: Descent, thresholds: Thresholds, log: list[Decision]
) -> tuple[Path, list[Placement] | None] | NotSure:
    """The best path, with the second when the first is below `place_show_second`; below `place_min`, a question."""
    first = descent.ranked[0]
    unsure = first.landing == "none" or first.probability < thresholds.place_min
    action = "ask_top_3" if unsure else f"place {tree.path(first.node) or 'raiz'}"
    descent.decisions[-1] = descent.decisions[-1].model_copy(
        update={"threshold": thresholds.place_min, "action": action}
    )
    log.extend(descent.decisions)
    if unsure:
        return NotSure(options=placements(tree, descent.ranked[:3]))
    second = first.probability < thresholds.place_show_second
    return first, (placements(tree, descent.ranked[1:2]) or None) if second else None


async def file_text(
    source: CardInput,
    tree: TreeSnapshot,
    read_page: ReadPage,
    decider: Decider,
    writer: Writer,
    thresholds: Thresholds,
    log: list[Decision],
) -> Filed:
    card = await writer.card(source)
    state = card_state(card)
    descent = await descend(state, tree, decider, text_options, STEP, "Onde guardar esta informação?")
    placed = place(tree, descent, thresholds, log)
    if isinstance(placed, NotSure):
        unplaced = await build.create_page(writer, card, tree, _likeliest(tree, placed.options))
        return placed.model_copy(update={"payload": unplaced})
    path, alternatives = placed
    if path.landing != "node" or path.node is None:
        return Propose(payload=await build.create_page(writer, card, tree, path.node), alternatives=alternatives)

    page = await read_page(path.node.id)
    check = await check_page(state, page, decider, thresholds, log)
    page_path = tree.path(path.node)
    if check.covered:
        return AlreadyWritten(
            page_id=page.page_id, path=page_path, anchor=check.section.anchor, heading=check.section.heading
        )
    if check.contradicts:
        payload: ProposalPayload = await build.conflict(writer, card, page, page_path, check)
    else:
        payload = await build.patch(writer, card, page, page_path, check)
    return Propose(payload=payload, alternatives=alternatives)


async def file_pdf(
    source: CardInput,
    tree: TreeSnapshot,
    decider: Decider,
    writer: Writer,
    thresholds: Thresholds,
    log: list[Decision],
) -> Propose | NotSure:
    """`source` holds the PDF's first pages and outline only, never the whole PDF."""
    card = await writer.card(source)
    state = card_state(card)
    descent = await descend(state, tree, decider, pdf_options, STEP, "Onde salvar este PDF?")
    placed = place(tree, descent, thresholds, log)
    if isinstance(placed, NotSure):
        unplaced = build.save_pdf(tree, _likeliest(tree, placed.options), source.file_name or card.title)
        return placed.model_copy(update={"payload": unplaced})
    path, alternatives = placed
    replaced = await replaced_pdf(state, tree, path.node, decider, thresholds, log)
    if replaced is not None:
        return Propose(payload=build.replace_pdf(tree, replaced), alternatives=alternatives)
    name = card.file_name or source.file_name or card.title
    return Propose(payload=build.save_pdf(tree, path.node, name), alternatives=alternatives)
