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
    taken: set[str] = set()
    in_code = False
    for line in markdown.splitlines():
        if line.startswith(("```", "~~~")):
            in_code = not in_code
        match = None if in_code else _HEADING.match(line)
        if match is None:
            continue
        heading = match.group(1)
        # "" is the text before the first heading, so a heading of only emoji or punctuation needs a slug of its own.
        base = slug(heading) or "secao"
        anchor, count = base, 1
        while anchor in taken:
            count += 1
            anchor = f"{base}-{count}"
        taken.add(anchor)
        found.append(Section(anchor, heading))
    return found
