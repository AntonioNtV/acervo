from uuid import UUID

from acervo.core.errors import ConflictError, TitleTaken, ValidationError
from acervo.domain.sort_keys import key_between
from acervo.pipeline.curator.tree import SnapshotNode, TreeSnapshot
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.file import FileResponse
from acervo.schemas.node import (
    NodeAdd,
    NodeCreate,
    NodeEdit,
    NodeKind,
    NodeMove,
    NodeRead,
    NodeUpdate,
    NodeWithPath,
    RestoredNode,
    TreeNode,
)
from acervo.schemas.page import NodeDetail, PageRead
from acervo.services.page_service import PageService


def _title(title: str) -> str:
    # Collapsed as link targets are, so `[[Foo  Bar]]` resolves to a page named "Foo  Bar"; Postgres refuses NUL.
    title = " ".join(title.replace("\x00", "").split())
    if not title:
        raise ValidationError("a title cannot be empty", {"title": title})
    return title


class TreeService:
    """The tree of a base: folders, pages and files, their order, moves, renames, search and the trash."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._pages = PageService(uow)

    async def detail(self, node_id: UUID) -> NodeDetail:
        """The live node with its path and, for a page, its text; for a file, its current content."""
        node = await self._uow.nodes.live(node_id)
        page: PageRead | None = None
        file: FileResponse | None = None
        versions = 0
        if node.kind == "page":
            page = await self._pages.read(node.id)
            versions = await self._uow.page_versions.count({"node_id": node.id})
        elif node.kind == "file":
            file = FileResponse.model_validate(await self._uow.files.of_node(node.id), from_attributes=True)
            versions = await self._uow.file_versions.count({"node_id": node.id}) + 1
        path = await self._uow.nodes.path(node.id)
        return NodeDetail(**node.model_dump(), path=path, page=page, file=file, versions=versions)

    async def children(self, kb_id: UUID, parent_id: UUID | None) -> list[TreeNode]:
        await self._uow.nodes.live_parent(kb_id, parent_id)
        return await self._uow.nodes.children(kb_id, parent_id)

    async def snapshot(self, kb_id: UUID) -> TreeSnapshot:
        """Every live node of the base with its description, parents before children, siblings in their order: what
        the pipeline decides over."""
        nodes: list[SnapshotNode] = []
        parents: list[UUID | None] = [None]
        while parents:
            for child in await self._uow.nodes.children(kb_id, parents.pop(0)):
                nodes.append(
                    SnapshotNode(
                        id=child.id,
                        parent_id=child.parent_id,
                        kind=child.kind,
                        title=child.title,
                        description=child.description,
                        active_at=child.updated_at,
                    )
                )
                if child.child_count:
                    parents.append(child.id)
        return TreeSnapshot(nodes=nodes)

    async def create(
        self, kb_id: UUID, data: NodeAdd, *, markdown: str = "", proposal_id: UUID | None = None, commit: bool = True
    ) -> NodeRead:
        """A new folder, or a page whose first version is `markdown`, by the agent of `proposal_id` when given.
        Without `commit`, in the caller's transaction."""
        title = _title(data.title)
        await self._uow.kbs.lock(kb_id)
        await self._uow.nodes.live_parent(kb_id, data.parent_id)
        await self._ensure_title_free(kb_id, data.parent_id, data.kind, title)
        sort = key_between(await self._uow.nodes.last_sort(kb_id, data.parent_id), None)
        node = await self._uow.nodes.create(
            NodeCreate(kb_id=kb_id, parent_id=data.parent_id, kind=data.kind, title=title, sort=sort)
        )
        if node.kind == "page":
            await self._pages.create(node, markdown, proposal_id)
        if commit:
            await self._uow.commit()
        return node

    async def edit(self, node_id: UUID, data: NodeEdit) -> NodeRead:
        """The person's change of title, description, icon or cover; their description is locked against agents.
        An icon or cover sent as null is removed; one left out is kept."""
        node = await self._uow.nodes.live(node_id)
        if data.cover is not None and node.kind == "file":
            raise ValidationError("um arquivo não tem capa", {"cover": data.cover})
        if data.title is not None:
            node = await self._rename(node, data.title)
        change = NodeUpdate(**data.model_dump(include={"icon", "cover"} & data.model_fields_set))
        if data.description is not None:
            description = data.description.strip()
            change.description = description
            change.description_locked = bool(description)
        if change.model_fields_set:
            node = await self._uow.nodes.update(node_id, change)
        await self._uow.commit()
        return node

    async def rename(
        self, node_id: UUID, title: str, *, proposal_id: UUID | None = None, commit: bool = True
    ) -> NodeRead:
        """A page's rename also fixes the links that resolve to it, in the same transaction; by the agent of
        `proposal_id` when given. Without `commit`, in the caller's transaction."""
        renamed = await self._rename(await self._uow.nodes.live(node_id), title, proposal_id)
        if commit:
            await self._uow.commit()
        return renamed

    async def _rename(self, node: NodeRead, title: str, proposal_id: UUID | None = None) -> NodeRead:
        node_id = node.id
        title = _title(title)
        await self._uow.kbs.lock(node.kb_id)
        if title.lower() != node.title.lower():
            await self._ensure_title_free(node.kb_id, node.parent_id, node.kind, title)
        if node.kind == "page" and title != node.title:
            await self._pages.fix_links(node, title, proposal_id)
        return await self._uow.nodes.update(node_id, NodeUpdate(title=title))

    async def move(self, node_id: UUID, data: NodeMove, *, commit: bool = True) -> NodeRead:
        """Puts the node in `parent_id` just before the sibling `before_id`, or last when it is None. Into another
        base, its whole subtree goes along. Without `commit`, in the caller's transaction."""
        nodes = self._uow.nodes
        node = await nodes.live(node_id)
        kb_id = data.kb_id or node.kb_id
        for locked in sorted({node.kb_id, kb_id}):
            await self._uow.kbs.lock(locked)
        await nodes.live_parent(kb_id, data.parent_id)
        if data.parent_id is not None and node.id in await nodes.ancestors(data.parent_id):
            raise ValidationError(
                "a node cannot move into itself or into a node inside it", {"parent_id": str(data.parent_id)}
            )
        if data.parent_id != node.parent_id or kb_id != node.kb_id:
            await self._ensure_title_free(kb_id, data.parent_id, node.kind, node.title)

        if data.before_id is None:
            sort = key_between(await nodes.last_sort(kb_id, data.parent_id, excluding=node.id), None)
        else:
            before = await nodes.live(data.before_id)
            if before.id == node.id or before.kb_id != kb_id or before.parent_id != data.parent_id:
                raise ValidationError(
                    f"node {data.before_id} is not a sibling at the destination", {"before_id": str(data.before_id)}
                )
            previous = await nodes.last_sort(kb_id, data.parent_id, below=before.sort, excluding=node.id)
            sort = key_between(previous, before.sort)
        if kb_id != node.kb_id:
            await self._change_base(node, kb_id)
        moved = await nodes.update(node_id, NodeUpdate(parent_id=data.parent_id, sort=sort))
        if commit:
            await self._uow.commit()
        return moved

    async def _change_base(self, node: NodeRead, kb_id: UUID) -> None:
        """The node's subtree, trashed nodes included, into base `kb_id`; refused when one of its files is already
        there. The links the move would break become text first."""
        subtree = await self._uow.nodes.subtree(node.id)
        ids = [moved.id for moved in subtree]
        held = await self._uow.files.held_in(kb_id, ids)
        if held:
            raise ConflictError("já está na base de destino", {"files": held})
        await self._pages.unlink_moved(subtree)
        await self._uow.nodes.set_base(ids, kb_id)
        await self._uow.page_links.set_base(ids, kb_id)

    async def trash(self, node_id: UUID, *, commit: bool = True) -> NodeRead:
        """Without `commit`, in the caller's transaction."""
        node = await self._uow.nodes.live(node_id)
        await self._uow.kbs.lock(node.kb_id)
        await self._uow.nodes.trash_subtree(node_id)
        trashed = await self._uow.nodes.trashed_root(node_id)
        if commit:
            await self._uow.commit()
        return trashed

    async def trash_of(self, kb_id: UUID) -> list[NodeWithPath]:
        """One item per trashing, most recent first, with where it was when it was trashed."""
        nodes = await self._uow.nodes.trash_roots(kb_id)
        return await self._with_paths(nodes)

    async def restore(self, node_id: UUID) -> RestoredNode:
        nodes = self._uow.nodes
        node = await nodes.trashed_root(node_id)
        await self._uow.kbs.lock(node.kb_id)
        to_root = node.parent_id is not None and await nodes.is_trashed(node.parent_id)
        parent_id = None if to_root else node.parent_id
        await self._ensure_title_free(node.kb_id, parent_id, node.kind, node.title)
        if to_root:
            sort = key_between(await nodes.last_sort(node.kb_id, None), None)
            await nodes.update(node_id, NodeUpdate(parent_id=None, sort=sort))
        elif await nodes.sort_taken(node.kb_id, parent_id, node.sort):
            # A node placed while this one was in the trash took its key.
            sort = key_between(node.sort, await nodes.next_sort(node.kb_id, parent_id, node.sort))
            await nodes.update(node_id, NodeUpdate(sort=sort))
        await nodes.restore_trashed_with(node_id)
        restored = await nodes.live(node_id)
        await self._uow.commit()
        return RestoredNode(**restored.model_dump(), to_root=to_root)

    async def search(self, kb_id: UUID, query: str) -> list[NodeWithPath]:
        query = query.strip()
        if not query:
            return []
        return await self._with_paths(await self._uow.nodes.search(kb_id, query))

    async def _with_paths(self, nodes: list[NodeRead]) -> list[NodeWithPath]:
        found = await self._uow.nodes.paths([node.id for node in nodes])
        return [NodeWithPath(**node.model_dump(), path=found[node.id]) for node in nodes]

    async def _ensure_title_free(self, kb_id: UUID, parent_id: UUID | None, kind: NodeKind, title: str) -> None:
        if await self._uow.nodes.title_taken(kb_id, parent_id, kind, title):
            raise TitleTaken("já existe", {"title": title})
