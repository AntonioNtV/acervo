import httpx

from acervo.api.cookies import SESSION_COOKIE
from tests.services.test_passkey_service import SoftAuthenticator


async def test_a_passkey_added_signs_in_with_no_password(
    client: httpx.AsyncClient, anon_client: httpx.AsyncClient
) -> None:
    authenticator = SoftAuthenticator()

    options = await client.post("/v1/passkeys/register/options")
    assert options.status_code == 200
    assert options.json()["options"]["authenticatorSelection"]["residentKey"] == "required"
    added = await client.post(
        "/v1/passkeys/register", json={"credential": authenticator.create(options.json()["options"])}
    )
    assert added.status_code == 201, added.text
    listed = await client.get("/v1/passkeys")
    assert [passkey["name"] for passkey in listed.json()] == ["1Password"]

    options = await anon_client.post("/v1/passkeys/sign-in/options")
    assert options.json()["options"].get("allowCredentials", []) == []
    authenticator.sign_count = 1
    signed_in = await anon_client.post(
        "/v1/passkeys/sign-in", json={"credential": authenticator.get(options.json()["options"])}
    )

    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["has_passkey"] is True
    assert SESSION_COOKIE in signed_in.cookies
    assert (await anon_client.get("/v1/account")).status_code == 200
