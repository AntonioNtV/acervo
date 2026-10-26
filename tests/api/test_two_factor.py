import httpx
from fastapi import FastAPI

from acervo.api.cookies import PENDING_COOKIE, SESSION_COOKIE
from acervo.services.mailer import FakeMailer, MailTemplate
from tests.conftest import DEFAULT_EMAIL


async def test_with_two_factor_a_password_sign_in_waits_for_the_emailed_code(
    client: httpx.AsyncClient, anon_client: httpx.AsyncClient, app: FastAPI
) -> None:
    turned_on = await client.post("/v1/two-factor", json={"method": "email"})

    signed = await anon_client.post("/v1/auth/sign-in", json={"email": DEFAULT_EMAIL, "password": "senha-de-teste"})
    assert (turned_on.status_code, turned_on.json()["two_factor"]) == (200, "email")
    assert (signed.status_code, signed.json()["pending"], signed.json()["method"]) == (200, True, "email")
    assert (PENDING_COOKIE in anon_client.cookies, SESSION_COOKIE in anon_client.cookies) == (True, False)

    mailer: FakeMailer = app.state.mailer
    assert mailer.sent[-1].template == MailTemplate.LOGIN_CODE
    finished = await anon_client.post("/v1/auth/two-factor", json={"code": mailer.sent[-1].values["code"]})
    me = await anon_client.get("/v1/auth/me")

    assert (finished.status_code, PENDING_COOKIE in anon_client.cookies) == (200, False)
    assert (me.status_code, me.json()["email"]) == (200, DEFAULT_EMAIL)
