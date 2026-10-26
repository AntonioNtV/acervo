from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI

from acervo.api.cookies import SESSION_COOKIE
from acervo.api.routers.google import STATE_COOKIE, get_google_client
from acervo.services.google_client import GoogleClient, GoogleIdentity


class FakeGoogle(GoogleClient):
    def __init__(self) -> None:
        super().__init__("client-id", "client-secret")

    async def identity(self, code: str, code_verifier: str, redirect_uri: str) -> GoogleIdentity:
        return GoogleIdentity(sub="google-1", email="ana@example.com", email_verified=True, name="Ana")


@pytest.fixture(autouse=True)
def fake_google(app: FastAPI) -> None:
    app.dependency_overrides[get_google_client] = FakeGoogle


async def _start(client: httpx.AsyncClient) -> str:
    response = await client.get("/v1/auth/google/start", params={"next": "/kbs/1"})
    assert response.status_code == 302
    assert STATE_COOKIE in response.cookies
    location = urlsplit(response.headers["location"])
    assert (location.netloc, location.path) == ("accounts.google.com", "/o/oauth2/v2/auth")
    query = parse_qs(location.query)
    assert query["scope"] == ["openid email profile"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["http://localhost:5173/v1/auth/google/callback"]
    return query["state"][0]


async def test_start_sets_the_state_cookie_and_redirects_to_google(client: httpx.AsyncClient) -> None:
    await _start(client)


async def test_callback_signs_in_and_opens_next(client: httpx.AsyncClient) -> None:
    state = await _start(client)

    response = await client.get("/v1/auth/google/callback", params={"code": "c", "state": state})

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173/kbs/1"
    assert SESSION_COOKIE in response.cookies
    replay = await client.get("/v1/auth/google/callback", params={"code": "c", "state": state})
    assert replay.headers["location"] == "http://localhost:5173/entrar?erro=google"


async def test_callback_refuses_a_forged_state(client: httpx.AsyncClient) -> None:
    await _start(client)

    response = await client.get("/v1/auth/google/callback", params={"code": "c", "state": "forged"})

    assert response.headers["location"] == "http://localhost:5173/entrar?erro=google"
    assert SESSION_COOKIE not in response.cookies
