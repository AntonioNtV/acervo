import json
import time
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from acervo.services import google_client
from acervo.services.google_client import GoogleClient, GoogleError

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
REDIRECT_URI = "http://localhost:5173/v1/auth/google/callback"


def _claims(**changes: Any) -> dict[str, Any]:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "client-id",
        "exp": int(time.time()) + 300,
        "sub": "google-1",
        "email": "ana@example.com",
        "email_verified": True,
        "name": "Ana Google",
    }
    return claims | changes


def _sign(claims: dict[str, Any], kid: str = "key-1") -> str:
    return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": kid})


def _client(id_token: str) -> GoogleClient:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key())) | {"kid": "key-1", "alg": "RS256"}

    def google(request: httpx.Request) -> httpx.Response:
        if request.url == google_client.JWKS_URL:
            return httpx.Response(200, json={"keys": [jwk]}, headers={"cache-control": "public, max-age=3600"})
        return httpx.Response(200, json={"id_token": id_token})

    return GoogleClient("client-id", "client-secret", httpx.MockTransport(google))


@pytest.fixture(autouse=True)
def _no_cached_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(google_client, "_keys", {})
    monkeypatch.setattr(google_client, "_keys_until", 0.0)


async def test_a_token_signed_by_google_gives_the_person() -> None:
    person = await _client(_sign(_claims())).identity("code", "verifier", REDIRECT_URI)

    assert (person.sub, person.email, person.email_verified, person.name) == (
        "google-1",
        "ana@example.com",
        True,
        "Ana Google",
    )


def _tampered() -> str:
    header, _, signature = _sign(_claims()).split(".")
    payload = jwt.utils.base64url_encode(json.dumps(_claims(sub="google-2")).encode()).decode()
    return f"{header}.{payload}.{signature}"


def _unsigned() -> str:
    return jwt.encode(_claims(), None, algorithm="none", headers={"kid": "key-1"})


@pytest.mark.parametrize(
    "id_token",
    [
        pytest.param(_tampered(), id="tampered payload"),
        pytest.param(_sign(_claims(aud="other-client")), id="wrong audience"),
        pytest.param(_sign(_claims(iss="https://evil.example")), id="wrong issuer"),
        pytest.param(_sign(_claims(exp=int(time.time()) - 1)), id="expired"),
        pytest.param(_sign(_claims(), kid="key-2"), id="unknown kid"),
        pytest.param(_unsigned(), id="alg none"),
    ],
)
async def test_a_token_that_fails_a_check_is_refused(id_token: str) -> None:
    with pytest.raises(GoogleError):
        await _client(id_token).identity("code", "verifier", REDIRECT_URI)
