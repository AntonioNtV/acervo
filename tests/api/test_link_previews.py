from collections.abc import Callable

import httpx
import pytest
from fastapi import FastAPI

from acervo.api.deps import get_link_preview_service
from acervo.services.link_preview_service import LinkPreviewService

# Literal public addresses, so the host check needs no DNS.
SITE = "http://93.184.215.14"
OTHER = "https://8.8.8.8"

Handler = Callable[[httpx.Request], httpx.Response]


def _stub(app: FastAPI, handler: Handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    service = LinkPreviewService(5, 1024 * 1024, httpx.MockTransport(record))
    app.dependency_overrides[get_link_preview_service] = lambda: service
    return seen


def _html(body: str) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=body)


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1", "http://10.0.0.1", "http://[::1]", "http://localhost", "file:///etc/passwd", "nada"],
)
async def test_refused_addresses_are_422(client: httpx.AsyncClient, app: FastAPI, url: str) -> None:
    seen = _stub(app, lambda request: _html("<title>x</title>"))

    response = await client.get("/v1/link-preview", params={"url": url})

    assert response.status_code == 422, response.text
    assert response.json()["error"] == "link_not_allowed"
    assert seen == []


async def test_a_redirect_to_a_private_address_is_refused(client: httpx.AsyncClient, app: FastAPI) -> None:
    seen = _stub(app, lambda request: httpx.Response(302, headers={"location": "http://10.0.0.1/admin"}))

    response = await client.get("/v1/link-preview", params={"url": SITE})

    assert response.status_code == 422, response.text
    assert response.json()["error"] == "link_not_allowed"
    assert len(seen) == 1


async def test_open_graph_fields_after_a_redirect(client: httpx.AsyncClient, app: FastAPI) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "93.184.215.14":
            return httpx.Response(301, headers={"location": f"{OTHER}/post"})
        return _html('<meta property="og:title" content="Apólice 2026"><meta property="og:image" content="/capa.png">')

    seen = _stub(app, handler)

    response = await client.get("/v1/link-preview", params={"url": SITE})

    assert response.status_code == 200, response.text
    assert response.json() == {
        "url": SITE,
        "domain": "93.184.215.14",
        "title": "Apólice 2026",
        "description": None,
        "image": f"{OTHER}/capa.png",
    }
    assert [str(request.url) for request in seen] == [f"{SITE}", f"{OTHER}/post"]


async def test_title_only(client: httpx.AsyncClient, app: FastAPI) -> None:
    _stub(app, lambda request: _html("<title>Seguros</title>"))

    response = await client.get("/v1/link-preview", params={"url": f"{SITE}/a"})

    assert response.json()["title"] == "Seguros"


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("slow", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        _timeout,
        lambda request: httpx.Response(500),
        lambda request: httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF"),
        lambda request: httpx.Response(302, headers={"location": request.url.path + "x"}),
    ],
    ids=["timeout", "error", "not-html", "too-many-redirects"],
)
async def test_a_site_that_fails_gives_only_the_domain(
    client: httpx.AsyncClient, app: FastAPI, handler: Handler
) -> None:
    _stub(app, handler)

    response = await client.get("/v1/link-preview", params={"url": SITE})

    assert response.status_code == 200, response.text
    assert response.json() == {
        "url": SITE,
        "domain": "93.184.215.14",
        "title": None,
        "description": None,
        "image": None,
    }
