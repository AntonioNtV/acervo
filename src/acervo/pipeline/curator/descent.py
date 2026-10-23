"""Down the tree from the root, one Choice per level, keeping the two best paths (skill `curator-agent`)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from acervo.domain.cards import Placement
from acervo.domain.decisions import Choice
from acervo.model_clients.decider import Decider
from acervo.pipeline.curator.log import record
from acervo.pipeline.curator.options import Landing, Options
from acervo.pipeline.curator.tree import SnapshotNode, TreeSnapshot
from acervo.schemas.proposal import Decision

PlacementLanding = Literal["page", "here", "new_page", "new_folder"]

BEAM = 2
MAX_DEPTH = 6


@dataclass(frozen=True)
class Path:
    node: SnapshotNode | None
    # The product of the chosen options' probabilities.
    probability: float
    # None while it can still go down.
    landing: Landing | None = None


@dataclass
class Descent:
    # Most likely first: every place reached and the last level's paths, so a top 3 can be offered.
    ranked: list[Path]
    decisions: list[Decision] = field(default_factory=list)


async def descend(
    state: str,
    tree: TreeSnapshot,
    decider: Decider,
    options: Options,
    step: str,
    question: str,
) -> Descent:
    """Every open path of the beam is one Choice; the Choices of a level go in one call, since the state is the
    same input. At the depth limit an open path stops where it is."""
    descent = Descent(ranked=[Path(None, 1.0)])
    for _ in range(MAX_DEPTH):
        beam = descent.ranked[:BEAM]
        open_paths = [path for path in beam if path.landing is None and path.probability > 0]
        if not open_paths:
            break
        levels = {f"{step}:{tree.path(path.node)}": (path, options(tree, path.node)) for path in open_paths}
        choices = [
            Choice(
                id=id,
                question=f"{question} Em: {tree.path(path.node) or 'raiz da base'}.",
                options=tuple(o.text for o in opts),
            )
            for id, (path, opts) in levels.items()
        ]
        answers = await decider.ask(state, choices)
        # A place already reached stays in the ranking: it costs no call and may beat a deeper one.
        candidates = [path for path in descent.ranked if path.landing is not None]
        for id, (path, opts) in levels.items():
            for option, probability in zip(opts, answers.probs[id], strict=True):
                candidates.append(Path(option.node or path.node, path.probability * probability, option.landing))
        descent.ranked = sorted(candidates, key=lambda path: -path.probability)
        kept = " | ".join(tree.path(path.node) or "raiz" for path in descent.ranked[:BEAM])
        descent.decisions += [record(answers, id, step, f"kept {kept}") for id in levels]
    descent.ranked = [path if path.landing else Path(path.node, path.probability, "here") for path in descent.ranked]
    return descent


def placement(tree: TreeSnapshot, path: Path) -> Placement:
    landing: PlacementLanding = (
        "page" if path.landing == "node" else "new_page" if path.landing == "new_page" else "here"
    )
    return Placement(
        node_id=path.node.id if path.node else None,
        path=tree.path(path.node),
        landing=landing,
        probability=round(path.probability, 4),
    )


def placements(tree: TreeSnapshot, paths: Sequence[Path]) -> list[Placement]:
    """Real places only: "none of these" is not one."""
    return [placement(tree, path) for path in paths if path.landing != "none"]
