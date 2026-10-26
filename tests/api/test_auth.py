from collections.abc import Awaitable, Callable

import httpx
from fastapi import FastAPI

from acervo.api.cookies import SESSION_COOKIE
from acervo.schemas.account import AccountRead
from acervo.services.mailer import FakeMailer

MakeAccount = Callable[..., Awaitable[AccountRead]]
PASSWORD = "senha-de-teste"


def mailer(app: FastAPI) -> FakeMailer:
    sent: FakeMailer = app.state.mailer
    return sent


async def test_sign_up_then_the_emailed_code_signs_in(anon_client: httpx.AsyncClient, app: FastAPI) -> None:
    created = await anon_client.post(
        "/v1/auth/sign-up", json={"name": "Ana", "email": "ana@example.com", "password": PASSWORD}
    )
    assert (created.status_code, created.json()["email_verified"], SESSION_COOKIE in anon_client.cookies) == (
        201,
        False,
        False,
    )

    code = mailer(app).sent[-1].values["code"]
    verified = await anon_client.post("/v1/auth/verify-email", json={"email": "ana@example.com", "code": code})
    me = await anon_client.get("/v1/auth/me")

    assert verified.status_code == 200
    assert (me.status_code, me.json()["id"], me.json()["email_verified"]) == (200, created.json()["id"], True)


async def test_sign_in_sets_an_http_only_lax_cookie(anon_client: httpx.AsyncClient, make_account: MakeAccount) -> None:
    await make_account(email="ana@example.com", password=PASSWORD)

    response = await anon_client.post("/v1/auth/sign-in", json={"email": "ana@example.com", "password": PASSWORD})

    cookie = response.headers["set-cookie"].lower()
    assert response.status_code == 200
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert ("httponly" in cookie, "samesite=lax" in cookie) == (True, True)


async def test_wrong_email_and_wrong_password_give_the_same_body(
    anon_client: httpx.AsyncClient, make_account: MakeAccount
) -> None:
    await make_account(email="ana@example.com", password=PASSWORD)

    wrong_email = await anon_client.post("/v1/auth/sign-in", json={"email": "bia@example.com", "password": PASSWORD})
    wrong_password = await anon_client.post(
        "/v1/auth/sign-in", json={"email": "ana@example.com", "password": "errada-errada"}
    )

    assert (wrong_email.status_code, wrong_email.json()["error"]) == (401, "invalid_credentials")
    assert wrong_email.content == wrong_password.content


async def test_after_sign_out_me_is_401(anon_client: httpx.AsyncClient, make_account: MakeAccount) -> None:
    await make_account(email="ana@example.com", password=PASSWORD)
    await anon_client.post("/v1/auth/sign-in", json={"email": "ana@example.com", "password": PASSWORD})
    token = anon_client.cookies[SESSION_COOKIE]

    signed_out = await anon_client.post("/v1/auth/sign-out")
    anon_client.cookies.clear()
    anon_client.cookies.set(SESSION_COOKIE, token)
    me = await anon_client.get("/v1/auth/me")

    assert (signed_out.status_code, me.status_code) == (204, 401)


async def test_a_password_reset_ends_the_other_sessions(
    anon_client: httpx.AsyncClient, app: FastAPI, make_account: MakeAccount
) -> None:
    await make_account(email="ana@example.com", password=PASSWORD)
    await anon_client.post("/v1/auth/sign-in", json={"email": "ana@example.com", "password": PASSWORD})
    other = anon_client.cookies[SESSION_COOKIE]

    asked = await anon_client.post("/v1/auth/reset", json={"email": "ana@example.com"})
    token = mailer(app).sent[-1].values["link"]
    confirmed = await anon_client.post("/v1/auth/reset/confirm", json={"token": token, "password": "nova-senha-longa"})
    me = await anon_client.get("/v1/auth/me")
    anon_client.cookies.clear()
    anon_client.cookies.set(SESSION_COOKIE, other)
    other_me = await anon_client.get("/v1/auth/me")

    assert (asked.status_code, confirmed.status_code, me.status_code, other_me.status_code) == (204, 200, 200, 401)
