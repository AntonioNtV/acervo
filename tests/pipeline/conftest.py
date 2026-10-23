import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any

import pytest

from acervo.core.settings import Thresholds
from acervo.pipeline.curator.tree import SnapshotNode, TreeSnapshot


@dataclass
class Snapshot:
    tree: TreeSnapshot
    # By path as written in the spec: "Bradesco/Residencial/Emissão de apólice.md".
    nodes: dict[str, SnapshotNode] = field(default_factory=dict)

    def __getitem__(self, path: str) -> SnapshotNode:
        return self.nodes[path]


def _children(spec: Any) -> list[tuple[str, Any]]:
    if spec is None:
        return []
    if isinstance(spec, dict):
        return list(spec.items())
    items: list[tuple[str, Any]] = []
    for item in spec:
        items += _children(item) if isinstance(item, dict) else [(item, None)]
    return items


@pytest.fixture
def make_snapshot() -> Callable[[Any], Snapshot]:
    """A tree snapshot from a dict, as `make_tree` takes it: `.md` names are pages, other names with an extension
    are files, names without one are folders; a page given children holds them. Later siblings are more recently
    active."""

    def make(spec: Any) -> Snapshot:
        nodes: list[SnapshotNode] = []
        by_path: dict[str, SnapshotNode] = {}
        start = datetime(2026, 1, 1, tzinfo=UTC)

        def add(parent: SnapshotNode | None, prefix: str, spec: Any) -> None:
            for index, (name, children) in enumerate(_children(spec)):
                suffix = PurePosixPath(name).suffix
                kind = "page" if suffix == ".md" else "file" if suffix else "folder"
                node = SnapshotNode(
                    id=uuid.uuid4(),
                    parent_id=parent.id if parent else None,
                    kind=kind,
                    title=name.removesuffix(".md"),
                    active_at=start + timedelta(minutes=index),
                )
                nodes.append(node)
                by_path[f"{prefix}{name}"] = node
                if kind != "file":
                    add(node, f"{prefix}{name}/", children)

        add(None, "", spec)
        return Snapshot(TreeSnapshot(nodes=nodes), by_path)

    return make


@pytest.fixture
def thresholds() -> Thresholds:
    return Thresholds()
