import ipaddress
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


@dataclass(frozen=True)
class PageMeta:
    title: str | None
    description: str | None
    image: str | None


def is_public(address: str) -> bool:
    """Whether an IP may be fetched: never loopback, private, link-local, multicast, reserved or unspecified."""
    ip = ipaddress.ip_address(address)
    return ip.is_global and not ip.is_multicast


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta" and values.get("content"):
            key = (values.get("property") or values.get("name") or "").lower()
            self.meta.setdefault(key, values["content"] or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def _clean(text: str | None) -> str | None:
    return " ".join((text or "").split()) or None


def parse(html: str, page_url: str) -> PageMeta:
    """Title, description and image of a page, from its Open Graph tags first; the image as an absolute http(s) URL."""
    parser = _MetaParser()
    parser.feed(html)
    meta = parser.meta
    image = _clean(meta.get("og:image"))
    image = urljoin(page_url, image) if image else None
    return PageMeta(
        title=_clean(meta.get("og:title")) or _clean(parser.title),
        description=_clean(meta.get("og:description")) or _clean(meta.get("description")),
        image=image if image and urlsplit(image).scheme in ("http", "https") else None,
    )
