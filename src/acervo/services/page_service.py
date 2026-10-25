from collections import defaultdict
from datetime import datetime, timedelta
from uuid import UUID

from acervo.core.errors import NotFoundError, StalePage, ValidationError
from acervo.domain import links
from acervo.domain.diff import line_diff
from acervo.domain.sections import sections
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.node import NodeRead, NodeWithPath
from acervo.schemas.page import (
    Mention,
    PageDiff,
    PageDraftCreate,
    PageDraftRead,
    PageRead,
    PageTextPut,
    PageTextSaved,
    PageVersionCreate,
    PageVersionRead,
    PageVersionSummary,
    Section,
)

MENTION_LINE_CHARS = 200


class PageService:
    """Markdown pages: the working text the person types, the versions cut from it, diffs and links."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def read(self, node_id: UUID) -> PageRead:
        """The text now with its revision, the newest version, where each link goes and the sections."""
        node = await self._page(node_id)
        version = await self._uow.page_versions.current(node.id)
        text = await self._uow.page_drafts.get_by(node_id=node.id)
        markdown = version.markdown if text is None else text.markdown
        wanted = await self._uow.page_links.targets(node.id)
        return PageRead(
            version_id=version.id,
            markdown=markdown,
            revision=0 if text is None else text.revision,
            saved_at=version.created_at if text is None else text.updated_at,
            links=links.resolve(wanted, await self._uow.page_links.candidates(node.kb_id, wanted), node.parent_id),
            sections=[Section(anchor=s.anchor, heading=s.heading) for s in sections(markdown)],
        )

    async def put_text(self, node_id: UUID, data: PageTextPut, idle_seconds: int) -> PageTextSaved:
        """The working text, saved as the person types; no version. After `idle_seconds` without a change, the
        session before is cut as a version first. A save from an older revision is refused: its text is kept as a
        version and the error carries the newest text and revision."""
        node = await self._page(node_id)
        await self._uow.kbs.lock(node.kb_id)
        latest = await self._uow.page_versions.current(node.id)
        text = await self._uow.page_drafts.get_by(node_id=node.id)
        revision = 0 if text is None else text.revision
        if data.revision != revision:
            if data.markdown != latest.markdown:
                await self._add(node, data.markdown)
            # Committed before raising: the refused text must outlive the rollback the error causes.
            await self._uow.commit()
            raise StalePage(
                f"page {node.id} changed since revision {data.revision}",
                {"markdown": latest.markdown if text is None else text.markdown, "revision": revision},
            )
        now = await self._uow.page_drafts.clock()
        if text is not None and now - text.updated_at > timedelta(seconds=idle_seconds):
            latest = await self._cut(node, text, latest)
        started_at = now if text is None or text.markdown == latest.markdown else text.started_at
        saved = await self._store(node, data.markdown, revision + 1, started_at)
        await self._uow.commit()
        return PageTextSaved(revision=saved.revision, saved_at=saved.updated_at)

    async def cut(self, node_id: UUID) -> None:
        """The working text as a version now, unless it is the newest version's text: when the person leaves."""
        await self._cut_now(await self._page(node_id))
        await self._uow.commit()

    async def versions(self, node_id: UUID) -> list[PageVersionSummary]:
        """Every version of the page, newest first, without its text, the working text cut first. Versions are never
        updated or deleted."""
        node = await self._page(node_id)
        await self._cut_now(node)
        await self._uow.commit()
        return await self._uow.page_versions.history(node.id)

    async def diff(self, node_id: UUID, version_id: UUID) -> PageDiff:
        """The version against the one before it; the first one against an empty page."""
        version = await self._version(await self._page(node_id), version_id)
        previous = await self._uow.page_versions.previous_markdown(version)
        return PageDiff.model_validate({"lines": line_diff(previous, version.markdown)})

    async def restore(self, node_id: UUID, version_id: UUID) -> PageRead:
        """The old text as a new version on top, and as the working text; the newer versions stay."""
        node = await self._page(node_id)
        version = await self._version(node, version_id)
        latest = await self._cut_now(node)
        await self._settle(node, version.markdown, latest, await self._uow.page_drafts.get_by(node_id=node.id))
        await self._uow.commit()
        return await self.read(node.id)

    async def mentions(self, node_id: UUID) -> list[Mention]:
        """Each live page of the base whose link opens this page, once, with the first line holding the link,
        ordered by path."""
        node = await self._page(node_id)
        target = links.normalize(node.title)
        candidates = await self._uow.page_links.candidates(node.kb_id, [target])
        linking = [
            page
            for page in await self._uow.page_links.linking(node.kb_id, target)
            if links.resolve([target], candidates, page.parent_id)[target] == node.id
        ]
        paths = await self._uow.nodes.paths([page.id for page in linking])
        mentions: list[Mention] = []
        for page in sorted(linking, key=lambda page: paths[page.id]):
            text = await self._uow.page_drafts.get_by(node_id=page.id)
            markdown = (await self._uow.page_versions.current(page.id)).markdown if text is None else text.markdown
            line = next((line.strip() for line in markdown.splitlines() if target in links.targets(line)), "")
            node_with_path = NodeWithPath(**page.model_dump(), path=paths[page.id])
            mentions.append(Mention(node=node_with_path, line=line[:MENTION_LINE_CHARS]))
        return mentions

    async def create(self, node: NodeRead) -> None:
        """The empty first version of a new page, in the caller's transaction."""
        await self._add(node, "")

    async def fix_links(self, node: NodeRead, new_title: str) -> list[PageVersionRead]:
        """A new version by the person, also set as the working text, of every live page whose link resolves to
        `node`, in the caller's transaction.

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
            text = await self._uow.page_drafts.get_by(node_id=page.id)
            current = latest.markdown if text is None else text.markdown
            markdown = links.rewrite(current, node.title, new_title)
            if markdown != current:
                fixed.append(await self._settle(page, markdown, latest, text))
        return fixed

    async def unlink_moved(self, moved: list[NodeRead]) -> None:
        """Turns into text the links that `moved`, a subtree going to another base, would break: in live pages left
        behind that link to a moved page, and in moved pages that link to a page left behind. Each changed page has
        its working text cut as a version first, then gets the new text as a version and as its working text.

        Called before the nodes change base, with both bases locked, in the caller's transaction.
        """
        kb_id = moved[0].kb_id
        moved_ids = {node.id for node in moved}
        pages = [node for node in moved if node.kind == "page" and node.deleted_at is None]
        broken: dict[UUID, set[str]] = defaultdict(set)
        holders: dict[UUID, NodeRead] = {}
        for page in pages:
            target = links.normalize(page.title)
            candidates = await self._uow.page_links.candidates(kb_id, [target])
            for linking in await self._uow.page_links.linking(kb_id, target):
                if linking.id in moved_ids:
                    continue
                if links.resolve([target], candidates, linking.parent_id)[target] == page.id:
                    broken[linking.id].add(target)
                    holders[linking.id] = linking
        for page in pages:
            wanted = await self._uow.page_links.targets(page.id)
            resolved = links.resolve(wanted, await self._uow.page_links.candidates(kb_id, wanted), page.parent_id)
            left_behind = {target for target, to in resolved.items() if isinstance(to, UUID) and to not in moved_ids}
            if left_behind:
                broken[page.id] |= left_behind
                holders[page.id] = page
        for page_id, targets in broken.items():
            page = holders[page_id]
            latest = await self._cut_now(page)
            markdown = links.unlink(latest.markdown, targets)
            if markdown != latest.markdown:
                await self._settle(page, markdown, latest, await self._uow.page_drafts.get_by(node_id=page.id))

    async def _cut_now(self, node: NodeRead) -> PageVersionRead:
        """The newest version once the working text is cut, under the base's lock."""
        await self._uow.kbs.lock(node.kb_id)
        latest = await self._uow.page_versions.current(node.id)
        text = await self._uow.page_drafts.get_by(node_id=node.id)
        return latest if text is None else await self._cut(node, text, latest)

    async def _cut(self, node: NodeRead, text: PageDraftRead, latest: PageVersionRead) -> PageVersionRead:
        if text.markdown == latest.markdown:
            return latest
        return await self._add(node, text.markdown, text.started_at, text.updated_at)

    async def _settle(
        self, node: NodeRead, markdown: str, latest: PageVersionRead, text: PageDraftRead | None
    ) -> PageVersionRead:
        """`markdown` as a version, unless it is the newest one's text, and as the working text `text` was, bumping
        its revision so an open editor reloads instead of overwriting it."""
        version = latest if markdown == latest.markdown else await self._add(node, markdown)
        await self._store(node, markdown, (0 if text is None else text.revision) + 1, version.created_at)
        return version

    async def _store(self, node: NodeRead, markdown: str, revision: int, started_at: datetime) -> PageDraftRead:
        """The working text and its links; the links follow what the person sees, so a rename finds them."""
        data = PageDraftCreate(node_id=node.id, markdown=markdown, revision=revision, started_at=started_at)
        text = await self._uow.page_drafts.put(data)
        await self._uow.page_links.replace(node.kb_id, node.id, links.targets(markdown))
        return text

    async def _add(
        self, node: NodeRead, markdown: str, started_at: datetime | None = None, ended_at: datetime | None = None
    ) -> PageVersionRead:
        data = PageVersionCreate(node_id=node.id, markdown=markdown, edit_started_at=started_at, edit_ended_at=ended_at)
        return await self._uow.page_versions.add(data)

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
