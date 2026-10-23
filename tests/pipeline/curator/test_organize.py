import uuid
from collections.abc import Callable
from typing import Any

from acervo.core.settings import Thresholds
from acervo.model_clients.fakes import FakeDecider
from acervo.pipeline.curator.organize import LastApplied, NothingToUndo, organize
from acervo.pipeline.curator.policy import Propose
from acervo.schemas.proposal import MovePayload, RenamePayload, UndoPayload

Make = Callable[[Any], Any]
TREE = {"Arquivo": [], "Bradesco": {"Auto": ["Tabela auto 2025.md"]}}
TABLE = "Bradesco/Auto/Tabela auto 2025.md"
TO_TABLE = {
    "organize_target:": {"Bradesco (pasta)": 1.0},
    "organize_target:Bradesco": {"Auto (pasta)": 1.0},
    "organize_target:Bradesco/Auto": {"Tabela auto 2025 (página)": 1.0},
}


async def test_a_move_is_resolved_to_the_node_and_its_destination(
    make_snapshot: Make, fake_decider: FakeDecider, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {
        "organize": [1.0, 0, 0],
        **TO_TABLE,
        "organize_destination:": {"Arquivo (pasta)": 1.0},
        "organize_destination:Arquivo": {"mover para cá": 1.0},
    }

    organized = await organize("Move a tabela auto 2025 para Arquivo", snap.tree, None, fake_decider, thresholds, [])

    assert organized == Propose(
        payload=MovePayload(
            node_id=snap[TABLE].id,
            from_path="Bradesco/Auto/Tabela auto 2025",
            parent_id=snap["Arquivo"].id,
            to_path="Arquivo",
        )
    )


async def test_a_rename_is_resolved_to_the_node(
    make_snapshot: Make, fake_decider: FakeDecider, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {"organize": [0, 1.0, 0], **TO_TABLE}

    organized = await organize(
        "renomeia a tabela auto 2025 para “Tabela auto 2026”", snap.tree, None, fake_decider, thresholds, []
    )

    assert organized == Propose(
        payload=RenamePayload(node_id=snap[TABLE].id, path="Bradesco/Auto/Tabela auto 2025", title="Tabela auto 2026")
    )


async def test_an_undo_is_resolved_to_the_last_applied_proposal(
    make_snapshot: Make, fake_decider: FakeDecider, thresholds: Thresholds
) -> None:
    snap = make_snapshot(TREE)
    fake_decider.table = {"organize": [0, 0, 1.0]}
    last = LastApplied(proposal_id=uuid.uuid4(), path="Bradesco/Auto/Tabela auto 2025")

    organized = await organize("desfaz a última mudança", snap.tree, last, fake_decider, thresholds, [])
    nothing = await organize("desfaz a última mudança", snap.tree, None, fake_decider, thresholds, [])

    assert organized == Propose(payload=UndoPayload(proposal_id=last.proposal_id, path=last.path))
    assert nothing == NothingToUndo()
    assert [[q.id for q in questions] for _, questions in fake_decider.calls] == [["organize"], ["organize"]]
