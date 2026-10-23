"""A move, rename or undo request resolved to nodes by decisions over the tree, never by searching titles."""

import re
from uuid import UUID

from pydantic import BaseModel

from acervo.core.settings import Thresholds
from acervo.domain.decisions import Choice
from acervo.model_clients.decider import Decider
from acervo.pipeline.curator.descent import descend
from acervo.pipeline.curator.log import Decision, best, record
from acervo.pipeline.curator.options import Option, Options, label, level
from acervo.pipeline.curator.policy import NotSure, Propose, place
from acervo.pipeline.curator.tree import SnapshotNode, TreeSnapshot
from acervo.schemas.proposal import MovePayload, RenamePayload, UndoPayload

KINDS = ("move", "rename", "undo")
KIND = Choice(
    id="organize",
    question="O que a pessoa pede para fazer na base?",
    options=(
        "mover um item para outra pasta",
        "renomear um item",
        "desfazer a última mudança aplicada",
    ),
)
THIS_FOLDER = Option("esta própria pasta", landing="here")
THIS_PAGE = Option("esta própria página", landing="here")
MOVE_HERE = Option("mover para cá", landing="here")
# The new name is what follows the last "para", "pra" or "como": "renomeia a tabela para Tabela 2026".
_NEW_TITLE = re.compile(r".*\s(?:para|pra|como)\s+(.+)$", re.IGNORECASE | re.DOTALL)


class LastApplied(BaseModel):
    """The proposal applied most recently in the base, which an undo reverts."""

    proposal_id: UUID
    path: str


class NeedsTitle(BaseModel):
    """A rename whose new name the message does not say."""

    node_id: UUID
    path: str


class NothingToUndo(BaseModel):
    """No applied proposal to undo."""


Organized = Propose | NotSure | NeedsTitle | NothingToUndo


def target_options(tree: TreeSnapshot, at: SnapshotNode | None) -> list[Option]:
    """Any child, a folder or a page with children to go into; inside one, that folder or page comes first."""

    def child(node: SnapshotNode) -> Option:
        container = node.kind == "folder" or bool(tree.children(node))
        return Option(label(node), node, None if container else "node")

    options = level(tree, at, child, [])
    if at is None:
        return options
    return [THIS_FOLDER if at.kind == "folder" else THIS_PAGE, *options]


def _destination_options(target: SnapshotNode) -> Options:
    def options(tree: TreeSnapshot, at: SnapshotNode | None) -> list[Option]:
        def child(node: SnapshotNode) -> Option | None:
            return Option(label(node), node) if node.kind == "folder" and node.id != target.id else None

        return level(tree, at, child, [MOVE_HERE])

    return options


def new_title(message: str) -> str | None:
    match = _NEW_TITLE.match(message.strip())
    title = match.group(1).strip().strip("\"'“”‘’.").strip() if match else ""
    return title or None


async def organize(
    message: str,
    tree: TreeSnapshot,
    last_applied: LastApplied | None,
    decider: Decider,
    thresholds: Thresholds,
    log: list[Decision],
) -> Organized:
    answers = await decider.ask(message, [KIND])
    kind = KINDS[best(answers, KIND.id)[0]]
    log.append(record(answers, KIND.id, "organize", kind))
    if kind == "undo":
        if last_applied is None:
            return NothingToUndo()
        return Propose(payload=UndoPayload(proposal_id=last_applied.proposal_id, path=last_applied.path))
    if not tree.nodes:
        return NotSure(options=[])

    question = "Qual item da base a pessoa quer mudar?"
    placed = place(
        tree, await descend(message, tree, decider, target_options, "organize_target", question), thresholds, log
    )
    if isinstance(placed, NotSure):
        return placed
    target = placed[0].node
    if target is None:
        return NotSure(options=[])
    if kind == "rename":
        title = new_title(message)
        if title is None:
            return NeedsTitle(node_id=target.id, path=tree.path(target))
        return Propose(payload=RenamePayload(node_id=target.id, path=tree.path(target), title=title))

    question = "Para qual pasta a pessoa quer mover o item?"
    descent = await descend(message, tree, decider, _destination_options(target), "organize_destination", question)
    placed = place(tree, descent, thresholds, log)
    if isinstance(placed, NotSure):
        return placed
    destination, alternatives = placed
    payload = MovePayload(
        node_id=target.id,
        from_path=tree.path(target),
        parent_id=destination.node.id if destination.node else None,
        to_path=tree.path(destination.node),
    )
    return Propose(payload=payload, alternatives=alternatives)
