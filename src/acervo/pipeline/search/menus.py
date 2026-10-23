"""The menus Jev routes with: a node's children plus "none", grouped when too many, packed several to a call."""

from collections.abc import Sequence
from itertools import batched
from math import ceil

from acervo.domain.decisions import Choice
from acervo.pipeline.search import questions
from acervo.pipeline.search.tree import SearchNode


def bounded(nodes: list[SearchNode], parent: str, size: int, chars: int) -> list[SearchNode]:
    """At most `size` options: past that, consecutive siblings are cut into groups, each an option of its own."""
    if len(nodes) <= size:
        return nodes
    step = max(size, ceil(len(nodes) / size))
    groups: list[SearchNode] = []
    for start in range(0, len(nodes), step):
        members = bounded(nodes[start : start + step], f"{parent}:group:{start}", size, chars)
        titles = "; ".join(member.title for member in members)
        groups.append(
            SearchNode(
                id=f"{parent}:group:{start}",
                node_id=None,
                kind="group",
                title="Grupo",
                path=[],
                built=titles[:chars],
                loaded=members,
            )
        )
    return groups


def menu(id: str, children: Sequence[SearchNode], query: str, chars: int) -> Choice:
    return questions.route(id, [child.describe(query)[:chars] for child in children])


def packs(menus: Sequence[Choice], per_call: int) -> list[tuple[Choice, ...]]:
    """The menus of one level, `per_call` to a Jev call: they share the state, the question searched."""
    return list(batched(menus, per_call))
