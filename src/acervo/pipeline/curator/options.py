"""The options of one level of the descent (skill `curator-agent`)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from acervo.pipeline.curator.tree import SnapshotNode, TreeSnapshot

# "node": the page chosen, or the page the level is at, written to; "here": under the node the level is at, or under
# the page chosen (a PDF); "none": none of the recent children.
Landing = Literal["node", "here", "new_page", "none"]

# Jev's Choice takes at most 255 options; past that, only the most recently active children are offered.
MAX_OPTIONS = 255
RECENT = 60

_KIND = {"folder": "pasta", "page": "página", "file": "arquivo"}


@dataclass(frozen=True)
class Option:
    text: str
    # The child it names; None for an option about the level itself.
    node: SnapshotNode | None = None
    # Where choosing it stops; None goes down into `node`, a folder or a page with children.
    landing: Landing | None = None


# At a page with children: that page itself. At a folder it would be a new page, so only NEW_PAGE is offered.
STAY = Option("ficar neste nível", landing="node")
NEW_PAGE = Option("nova página aqui", landing="new_page")
SAVE_HERE = Option("salvar aqui", landing="here")
NONE_OF_THESE = Option("nenhuma destas", landing="none")

Options = Callable[[TreeSnapshot, SnapshotNode | None], list[Option]]


def label(node: SnapshotNode) -> str:
    """A node as a decision option: its name, the person's description, then the one built from the index."""
    return " — ".join(filter(None, [f"{node.title} ({_KIND[node.kind]})", node.description, node.built]))


def level(
    tree: TreeSnapshot, at: SnapshotNode | None, child: Callable[[SnapshotNode], Option | None], last: list[Option]
) -> list[Option]:
    """The children `child` turns into options, then `last`; past 255, the 60 most recent and "none of these"."""
    children = [option for node in tree.children(at) if (option := child(node))]
    if len(children) + len(last) > MAX_OPTIONS:
        recent = sorted(
            children, key=lambda option: option.node.active_at if option.node else datetime.min, reverse=True
        )
        return [*recent[:RECENT], *last, NONE_OF_THESE]
    return [*children, *last]


def _container(tree: TreeSnapshot, node: SnapshotNode) -> bool:
    """A folder, or a page with children: an option to go down into."""
    return node.kind == "folder" or (node.kind == "page" and bool(tree.children(node)))


def text_options(tree: TreeSnapshot, at: SnapshotNode | None) -> list[Option]:
    """For a fact: the subfolders and the pages, a page with children to go into and one without to write to; at a
    page, "stay at this level" (that page) and "new page here"; elsewhere "new page here". Never a PDF."""

    def child(node: SnapshotNode) -> Option | None:
        if _container(tree, node):
            return Option(label(node), node)
        return Option(label(node), node, "node") if node.kind == "page" else None

    return level(tree, at, child, [STAY, NEW_PAGE] if at and at.kind == "page" else [NEW_PAGE])


def pdf_options(tree: TreeSnapshot, at: SnapshotNode | None) -> list[Option]:
    """For a PDF: the subfolders and the pages, a page with children to go into and one without to save under, and
    "save here". A PDF never lands in a page's text: under a page it is a file, as in a folder."""

    def child(node: SnapshotNode) -> Option | None:
        if _container(tree, node):
            return Option(label(node), node)
        return Option(label(node), node, "here") if node.kind == "page" else None

    return level(tree, at, child, [SAVE_HERE])
