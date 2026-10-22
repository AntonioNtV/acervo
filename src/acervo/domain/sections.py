import re
import unicodedata
from dataclasses import dataclass

_HEADING = re.compile(r"^## +(.+?)[ #]*$")


@dataclass(frozen=True)
class Section:
    anchor: str
    heading: str


def slug(heading: str) -> str:
    """`Emissão de apólice` → `emissao-de-apolice`."""
    ascii_text = unicodedata.normalize("NFKD", heading).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def sections(markdown: str) -> list[Section]:
    """The `##` headings of a page, each with an anchor unique in the page."""
    found: list[Section] = []
    seen: dict[str, int] = {}
    in_code = False
    for line in markdown.splitlines():
        if line.startswith(("```", "~~~")):
            in_code = not in_code
        match = None if in_code else _HEADING.match(line)
        if match is None:
            continue
        heading = match.group(1)
        anchor = slug(heading)
        seen[anchor] = seen.get(anchor, 0) + 1
        found.append(Section(anchor if seen[anchor] == 1 else f"{anchor}-{seen[anchor]}", heading))
    return found
