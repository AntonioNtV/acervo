import re
from collections import defaultdict
from collections.abc import Iterable
from typing import Literal, Protocol
from uuid import UUID

_LINK = re.compile(r"\[\[([^\[\]]+)\]\]")
_EMBED_OR_LINK = re.compile(r"!?\[\[([^\[\]]+)\]\]")

Resolved = UUID | Literal["missing", "ambiguous"]


class Page(Protocol):
    @property
    def id(self) -> UUID: ...
    @property
    def title(self) -> str: ...
    @property
    def parent_id(self) -> UUID | None: ...


def normalize(title: str) -> str:
    return " ".join(title.split()).lower()


def targets(markdown: str) -> set[str]:
    """The normalized titles inside the page's `[[…]]` links; `[[X#Section]]` and `![[X#Section]]` target X."""
    return {normalize(match.split("#", 1)[0]) for match in _LINK.findall(markdown)} - {""}


def resolve(wanted: Iterable[str], candidates: Iterable[Page], parent_id: UUID | None) -> dict[str, Resolved]:
    """Each target: the one live page with that title, else the one in the linking page's folder, else why not."""
    by_title: dict[str, list[Page]] = defaultdict(list)
    for candidate in candidates:
        by_title[normalize(candidate.title)].append(candidate)
    resolved: dict[str, Resolved] = {}
    for target in wanted:
        pages = by_title.get(target, [])
        same_folder = [page for page in pages if page.parent_id == parent_id]
        if len(pages) == 1:
            resolved[target] = pages[0].id
        elif len(same_folder) == 1:
            resolved[target] = same_folder[0].id
        else:
            resolved[target] = "ambiguous" if pages else "missing"
    return resolved


def rewrite(markdown: str, old_title: str, new_title: str) -> str:
    """Every `[[…]]` link to `old_title`, whatever its case and spacing, pointed at `new_title`, keeping its `#…`."""
    title = r"\s+".join(map(re.escape, old_title.split()))
    pattern = re.compile(r"\[\[\s*" + title + r"\s*(#[^\[\]]*)?\]\]", re.IGNORECASE)
    return pattern.sub(lambda m: f"[[{new_title}{m[1] or ''}]]", markdown)


def unlink(markdown: str, wanted: set[str]) -> str:
    """Every `[[…]]` or `![[…]]` link whose target is in `wanted` turned into its text, as the person wrote it."""
    return _EMBED_OR_LINK.sub(lambda m: m[1].strip() if normalize(m[1].split("#", 1)[0]) in wanted else m[0], markdown)
