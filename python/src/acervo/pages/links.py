import re
import uuid
from collections import defaultdict
from typing import Literal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.pages import versions
from acervo.store.models import Node, PageLink, PageVersion

_LINK = re.compile(r"\[\[([^\[\]]+)\]\]")

Resolved = uuid.UUID | Literal["missing", "ambiguous"]


def normalize(title: str) -> str:
    return " ".join(title.split()).lower()


def targets(markdown: str) -> set[str]:
    return {normalize(match) for match in _LINK.findall(markdown)} - {""}


async def index(session: AsyncSession, node: Node, markdown: str) -> None:
    """The page's rows in `page_link`, rewritten from the targets of its newest version."""
    await session.execute(delete(PageLink).where(PageLink.from_node_id == node.id))
    session.add_all(PageLink(kb_id=node.kb_id, from_node_id=node.id, target=target) for target in targets(markdown))
    await session.flush()


async def resolve(session: AsyncSession, node: Node) -> dict[str, Resolved]:
    """Each normalized target of the page: the page it opens, or why it shows in gray."""
    wanted = list(await session.scalars(select(PageLink.target).where(PageLink.from_node_id == node.id)))
    candidates = await session.scalars(
        select(Node).where(
            Node.kb_id == node.kb_id,
            Node.kind == "page",
            Node.deleted_at.is_(None),
            func.lower(Node.title).in_(wanted),
        )
    )
    by_title: dict[str, list[Node]] = defaultdict(list)
    for candidate in candidates:
        by_title[normalize(candidate.title)].append(candidate)
    resolved: dict[str, Resolved] = {}
    for target in wanted:
        pages = by_title.get(target, [])
        same_folder = [page for page in pages if page.parent_id == node.parent_id]
        if len(pages) == 1:
            resolved[target] = pages[0].id
        elif len(same_folder) == 1:
            resolved[target] = same_folder[0].id
        else:
            resolved[target] = "ambiguous" if pages else "missing"
    return resolved


async def fix_links(session: AsyncSession, kb_id: uuid.UUID, old_title: str, new_title: str) -> list[PageVersion]:
    """A new version by the person of every live page linking to `old_title`, found through `page_link` only."""
    linking = await session.scalars(
        select(Node)
        .join(PageLink, PageLink.from_node_id == Node.id)
        .where(PageLink.kb_id == kb_id, PageLink.target == normalize(old_title), Node.deleted_at.is_(None))
    )
    pattern = re.compile(r"\[\[\s*" + r"\s+".join(map(re.escape, old_title.split())) + r"\s*\]\]", re.IGNORECASE)
    fixed: list[PageVersion] = []
    for node in list(linking):
        latest = await versions.current(session, node.id)
        markdown = pattern.sub(lambda _: f"[[{new_title}]]", latest.markdown)
        if markdown != latest.markdown:
            fixed.append(await versions.add(session, node, markdown, "user"))
    return fixed
