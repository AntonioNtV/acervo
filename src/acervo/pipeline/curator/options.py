"""The options of one level of the descent (skill `curator-agent`)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from acervo.pipeline.curator.tree import SnapshotNode, TreeSnapshot

# "node": the chosen child itself; "here": the node the level is at; "none": none of the recent children.
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
    # Where choosing it stops; None goes down into `node`.
    landing: Landing | None = None


STAY = Option("ficar neste nível", landing="here")
NEW_PAGE = Option("nova página aqui", landing="new_page")
SAVE_HERE = Option("salvar aqui", landing="here")
NONE_OF_THESE = Option("nenhuma destas", landing="none")

Options = Callable[[TreeSnapshot, SnapshotNode | None], list[Option]]


def label(node: SnapshotNode) -> str:
    """A node as a decision option: its name and its description."""
    name = f"{node.title} ({_KIND[node.kind]})"
    return f"{name} — {node.description}" if node.description else name


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


def text_options(tree: TreeSnapshot, at: SnapshotNode | None) -> list[Option]:
    """For a fact: the subfolders, the pages, "stay at this level", "new page here". Never a PDF."""

    def child(node: SnapshotNode) -> Option | None:
        if node.kind == "folder":
            return Option(label(node), node)
        return Option(label(node), node, "node") if node.kind == "page" else None

    return level(tree, at, child, [STAY, NEW_PAGE])


def pdf_options(tree: TreeSnapshot, at: SnapshotNode | None) -> list[Option]:
    """For a PDF: the subfolders and "save here". A PDF never lands on a page."""
    return level(tree, at, lambda node: Option(label(node), node) if node.kind == "folder" else None, [SAVE_HERE])
