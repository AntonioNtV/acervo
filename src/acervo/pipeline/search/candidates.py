"""A shortcut: documents whose title or headings share the question's terms, offered as one more branch.

They are still routed and their passages scored by Jev; the branch only puts them a level from the top.
"""

import math
from collections.abc import Sequence
from dataclasses import replace

from acervo.pipeline.search.previews import terms
from acervo.pipeline.search.tree import SearchNode

CANDIDATES = 8
BRANCH = (
    "Documentos cujo título ou títulos de seção têm termos da pergunta. Localizam fontes; os fatos ainda precisam ser "
    "verificados."
)


def _outline(node: SearchNode) -> str:
    return node.built if isinstance(node.built, str) else ""


def candidate_branch(documents: Sequence[SearchNode], query: str, chars: int) -> SearchNode | None:
    """Up to CANDIDATES documents, the rarest shared terms first; None when none matches well enough."""
    wanted = set(terms(query))
    words = [set(terms(f"{doc.title}\n{_outline(doc)}")) for doc in documents]
    frequency = {term: sum(term in found for found in words) for term in wanted}
    ranked: list[tuple[float, SearchNode]] = []
    for doc, found in zip(documents, words, strict=True):
        weights = [2 * math.log(1 + len(documents) / (1 + frequency[term])) for term in wanted & found]
        # One common term alone is not a match.
        if not weights or (len(weights) == 1 and weights[0] < 2):
            continue
        headings = [h.strip() for h in _outline(doc).replace("\n", ";").split(";") if wanted & set(terms(h))]
        ranked.append((sum(weights), replace(doc, built="; ".join(headings) or _outline(doc))))
    if not ranked:
        return None
    ranked.sort(key=lambda pair: (-pair[0], pair[1].id))
    members = [doc for _, doc in ranked[:CANDIDATES]]
    share = chars // len(members)
    hints = "\n".join(member.describe(query)[:share] for member in members)
    return SearchNode(
        id="candidates",
        node_id=None,
        kind="group",
        title="Atalho",
        path=[],
        built=f"{BRANCH}\n{hints}"[:chars],
        loaded=members,
    )
