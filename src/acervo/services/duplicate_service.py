from uuid import UUID

from acervo.core.errors import ValidationError
from acervo.domain import links
from acervo.domain.sort_keys import key_between
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.node import NodeCreate, NodeRead
from acervo.schemas.page import PageVersionCreate


class DuplicateService:
    """A copy of a page and its sub-pages, with their working texts; files are never copied (a PDF stays a PDF)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def duplicate(self, node_id: UUID) -> NodeRead:
        """The copy, titled "<título> (cópia)", then "(cópia 2)", … while taken, right after the page."""
        nodes = self._uow.nodes
        page = await nodes.live(node_id)
        if page.kind != "page":
            raise ValidationError(f"node {node_id} is not a page", {"id": str(node_id)})
        await self._uow.kbs.lock(page.kb_id)
        sort = key_between(page.sort, await nodes.next_sort(page.kb_id, page.parent_id, page.sort))
        copy = await self._copy(page, page.parent_id, sort)
        await self._uow.commit()
        return copy

    async def _free_title(self, page: NodeRead, parent_id: UUID | None) -> str:
        title, count = f"{page.title} (cópia)", 1
        while await self._uow.nodes.title_taken(page.kb_id, parent_id, "page", title):
            count += 1
            title = f"{page.title} (cópia {count})"
        return title

    async def _copy(self, page: NodeRead, parent_id: UUID | None, sort: str) -> NodeRead:
        copy = await self._uow.nodes.create(
            NodeCreate(
                kb_id=page.kb_id,
                parent_id=parent_id,
                kind="page",
                title=await self._free_title(page, parent_id),
                sort=sort,
                description=page.description,
            ),
            description_locked=page.description_locked,
            icon=page.icon,
            cover=page.cover,
        )
        text = await self._uow.page_drafts.get_by(node_id=page.id)
        markdown = (await self._uow.page_versions.current(page.id)).markdown if text is None else text.markdown
        await self._uow.page_versions.add(PageVersionCreate(node_id=copy.id, markdown=markdown, author="user"))
        await self._uow.page_links.replace(copy.kb_id, copy.id, links.targets(markdown))
        # Sub-pages are renamed too, so a `[[link]]` to an original still resolves to that one page.
        for child in await self._uow.nodes.children(page.kb_id, page.id):
            if child.kind == "page":
                await self._copy(child, copy.id, child.sort)
        return copy
