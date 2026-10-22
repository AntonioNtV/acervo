from uuid import UUID

from acervo.core.errors import NotFoundError, StalePage, ValidationError
from acervo.domain import links
from acervo.domain.diff import line_diff
from acervo.domain.sections import sections
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.node import NodeRead
from acervo.schemas.page import (
    DraftPut,
    PageDiff,
    PageDraftCreate,
    PageDraftRead,
    PageRead,
    PageSave,
    PageVersionCreate,
    PageVersionRead,
    PageVersionSummary,
    Section,
)


class PageService:
    """Markdown pages: versions, drafts, diffs and links."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def read(self, node_id: UUID) -> PageRead:
        """The current text with its version, the draft, where each link goes and the sections."""
        node = await self._page(node_id)
        version = await self._uow.page_versions.current(node.id)
        wanted = await self._uow.page_links.targets(node.id)
        return PageRead(
            version_id=version.id,
            markdown=version.markdown,
            draft=await self._uow.page_drafts.get_by(node_id=node.id),
            links=links.resolve(wanted, await self._uow.page_links.candidates(node.kb_id, wanted), node.parent_id),
            sections=[Section(anchor=s.anchor, heading=s.heading) for s in sections(version.markdown)],
        )

    async def save(self, node_id: UUID, data: PageSave) -> PageVersionSummary:
        """A new whole-file version, unless the text is the current one. A stale base refuses, unless `force`."""
        node = await self._page(node_id)
        version = await self._save(node, data.markdown, data.base_version_id, force=data.force)
        await self._uow.commit()
        return version

    async def put_draft(self, node_id: UUID, data: DraftPut) -> PageDraftRead:
        """The page's single draft, replaced on every autosave. Never a version."""
        node = await self._page(node_id)
        draft = await self._uow.page_drafts.put(PageDraftCreate(node_id=node.id, **data.model_dump()))
        await self._uow.commit()
        return draft

    async def discard_draft(self, node_id: UUID) -> None:
        node = await self._page(node_id)
        await self._uow.page_drafts.discard(node.id)
        await self._uow.commit()

    async def versions(self, node_id: UUID) -> list[PageVersionSummary]:
        """Every version of the page, newest first, without its text. Versions are never updated or deleted."""
        node = await self._page(node_id)
        return await self._uow.page_versions.history(node.id)

    async def diff(self, node_id: UUID, version_id: UUID) -> PageDiff:
        """The version against the one before it; the first one against an empty page."""
        version = await self._version(await self._page(node_id), version_id)
        previous = await self._uow.page_versions.previous_markdown(version)
        return PageDiff.model_validate({"lines": line_diff(previous, version.markdown)})

    async def restore(self, node_id: UUID, version_id: UUID) -> PageRead:
        """The old text as a new version on top; the newer versions stay."""
        node = await self._page(node_id)
        version = await self._version(node, version_id)
        latest = await self._uow.page_versions.current(node.id)
        await self._save(node, version.markdown, latest.id)
        await self._uow.commit()
        return await self.read(node.id)

    async def create(self, node: NodeRead) -> None:
        """The empty first version of a new page, in the caller's transaction."""
        await self._add(node, "")

    async def fix_links(self, node: NodeRead, new_title: str) -> list[PageVersionRead]:
        """A new version by the person of every live page whose link resolves to `node`, in the caller's transaction.

        Called before the rename, with the base locked: once the title changes, those links no longer resolve to it.
        """
        target = links.normalize(node.title)
        fixed: list[PageVersionRead] = []
        # The same candidates for every linking page; only its folder can change where the link goes.
        candidates = await self._uow.page_links.candidates(node.kb_id, [target])
        for page in await self._uow.page_links.linking(node.kb_id, target):
            if links.resolve([target], candidates, page.parent_id)[target] != node.id:
                continue
            latest = await self._uow.page_versions.current(page.id)
            markdown = links.rewrite(latest.markdown, node.title, new_title)
            if markdown != latest.markdown:
                fixed.append(await self._add(page, markdown))
        return fixed

    async def _save(
        self, node: NodeRead, markdown: str, base_version_id: UUID, *, force: bool = False
    ) -> PageVersionSummary:
        latest = await self._uow.page_versions.current(node.id)
        if markdown == latest.markdown:
            await self._uow.page_drafts.discard(node.id)
            return latest
        if base_version_id != latest.id and not force:
            base = await self._uow.page_versions.get(base_version_id)
            raise StalePage(
                f"page {node.id} changed since version {base_version_id}",
                {
                    "current_version_id": str(latest.id),
                    "markdown": latest.markdown,
                    "diff": line_diff(base.markdown, latest.markdown),
                },
            )
        await self._uow.page_drafts.discard(node.id)
        return await self._add(node, markdown)

    async def _add(self, node: NodeRead, markdown: str) -> PageVersionRead:
        """A new version by the person and its links, nothing else: the draft stays, as on a rename's link fix."""
        data = PageVersionCreate(node_id=node.id, markdown=markdown, author="user")
        version = await self._uow.page_versions.add(data)
        await self._uow.page_links.replace(node.kb_id, node.id, links.targets(markdown))
        return version

    async def _page(self, node_id: UUID) -> NodeRead:
        node = await self._uow.nodes.live(node_id)
        if node.kind != "page":
            raise ValidationError(f"node {node_id} is not a page", {"id": str(node_id)})
        return node

    async def _version(self, node: NodeRead, version_id: UUID) -> PageVersionRead:
        version = await self._uow.page_versions.get(version_id)
        if version.node_id != node.id:
            raise NotFoundError(f"page_version {version_id} not found", {"id": str(version_id)})
        return version
