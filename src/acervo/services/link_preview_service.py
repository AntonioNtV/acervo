import asyncio
import socket
from dataclasses import asdict
from urllib.parse import urljoin

import httpx

from acervo.core.errors import ValidationError
from acervo.pipeline.link_preview import is_public, parse
from acervo.schemas.link_preview import LinkPreview

MAX_REDIRECTS = 3


class LinkNotAllowed(ValidationError):
    code = "link_not_allowed"


def _http_url(url: str) -> httpx.URL:
    try:
        parsed = httpx.URL(url)
    except httpx.InvalidURL:
        parsed = None
    if parsed is None or parsed.scheme not in ("http", "https") or not parsed.host:
        raise LinkNotAllowed("só links http ou https têm prévia", {"url": url})
    return parsed


async def _public_address(url: httpx.URL) -> str:
    """The address to connect to; refused when any address of the host is not public."""
    port = url.port or (443 if url.scheme == "https" else 80)
    infos = await asyncio.get_running_loop().getaddrinfo(url.host, port, type=socket.SOCK_STREAM)
    addresses = [str(info[4][0]) for info in infos]
    if not addresses or not all(is_public(address) for address in addresses):
        raise LinkNotAllowed("este endereço não pode ter prévia", {"url": str(url)})
    return addresses[0]


def _decode(body: bytes, charset: str | None) -> str:
    try:
        return body.decode(charset or "utf-8", errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


class LinkPreviewService:
    """Fetches what a site says about itself, only from public addresses and within a time and size limit."""

    def __init__(
        self, timeout_seconds: float, max_bytes: int, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._timeout = timeout_seconds
        self._max_bytes = max_bytes
        self._transport = transport

    async def preview(self, url: str) -> LinkPreview:
        """The page's title, description and image; only `url` and `domain` when the site fails or is too slow."""
        bare = LinkPreview(url=url, domain=_http_url(url).host)
        try:
            async with asyncio.timeout(self._timeout), httpx.AsyncClient(transport=self._transport) as client:
                current = url
                for _ in range(MAX_REDIRECTS + 1):
                    target = _http_url(current)
                    address = await _public_address(target)
                    # Connecting to the address just checked, so a second DNS answer cannot point somewhere else.
                    async with client.stream(
                        "GET",
                        target.copy_with(host=address),
                        headers={"Host": target.netloc.decode("ascii")},
                        extensions={"sni_hostname": target.host},
                    ) as response:
                        if response.is_redirect:
                            current = urljoin(current, response.headers["location"])
                            continue
                        content_type = response.headers.get("content-type", "").lower()
                        if not response.is_success or not content_type.startswith("text/html"):
                            return bare
                        body = await self._read(response)
                        meta = parse(_decode(body, response.charset_encoding), current)
                        return bare.model_copy(update=asdict(meta))
        except (TimeoutError, OSError, httpx.HTTPError):
            pass
        return bare

    async def _read(self, response: httpx.Response) -> bytes:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body += chunk
            if len(body) >= self._max_bytes:
                break
        return bytes(body[: self._max_bytes])
