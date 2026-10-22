import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from acervo.errors import ConflictError, NotFoundError
from acervo.pages import drafts, links
from acervo.pages.diff import line_diff
from acervo.store.models import Node, PageVersion
from acervo.store.repositories import get


async def current(session: AsyncSession, node_id: uuid.UUID) -> PageVersion:
    version = await session.scalar(
        select(PageVersion).where(PageVersion.node_id == node_id).order_by(PageVersion.created_at.desc()).limit(1)
    )
    if version is None:
        raise NotFoundError(f"page {node_id} has no version")
    return version


async def history(session: AsyncSession, node_id: uuid.UUID) -> list[PageVersion]:
    """Every version of the page, newest first, without its text. Versions are never updated or deleted."""
    query = (
        select(PageVersion)
        .options(defer(PageVersion.markdown, raiseload=True))
        .where(PageVersion.node_id == node_id)
        .order_by(PageVersion.created_at.desc())
    )
    return list(await session.scalars(query))


async def previous_markdown(session: AsyncSession, version: PageVersion) -> str:
    """The text of the version just before `version`; empty for the first one."""
    query = (
        select(PageVersion.markdown)
        .where(PageVersion.node_id == version.node_id, PageVersion.created_at < version.created_at)
        .order_by(PageVersion.created_at.desc())
        .limit(1)
    )
    return await session.scalar(query) or ""


async def add(session: AsyncSession, node: Node, markdown: str, author: str) -> PageVersion:
    """A new version and its links, nothing else: the draft stays, as when links are fixed on a rename."""
    # The database clock, not the transaction's: several versions written in one transaction keep their order.
    created_at = await session.scalar(select(func.clock_timestamp()))
    version = PageVersion(node_id=node.id, markdown=markdown, author=author, created_at=created_at)
    session.add(version)
    await session.flush()
    await links.index(session, node, markdown)
    return version


async def create(session: AsyncSession, node: Node, markdown: str = "") -> PageVersion:
    """The first version of a new page."""
    return await add(session, node, markdown, "user")


async def save(
    session: AsyncSession,
    node: Node,
    markdown: str,
    base_version_id: uuid.UUID,
    author: str = "user",
    force: bool = False,
) -> PageVersion:
    """A new whole-file version, unless the text is the current one. A stale base refuses, unless `force`."""
    latest = await current(session, node.id)
    if markdown == latest.markdown:
        await drafts.discard(session, node.id)
        return latest
    if base_version_id != latest.id and not force:
        base = await get(session, PageVersion, base_version_id)
        raise ConflictError(
            f"page {node.id} changed since version {base_version_id}",
            detail={
                "current_version_id": str(latest.id),
                "markdown": latest.markdown,
                "diff": line_diff(base.markdown, latest.markdown),
            },
        )
    await drafts.discard(session, node.id)
    return await add(session, node, markdown, author)


async def restore(session: AsyncSession, version_id: uuid.UUID) -> PageVersion:
    """The old text as a new version on top; the newer versions stay."""
    version = await get(session, PageVersion, version_id)
    node = await get(session, Node, version.node_id)
    latest = await current(session, node.id)
    return await save(session, node, version.markdown, latest.id)
