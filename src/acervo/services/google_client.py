import re
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from pydantic import BaseModel

from acervo.core.errors import AuthError

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")
TIMEOUT_SECONDS = 10

# Google's signing keys by `kid`, kept as long as Google's Cache-Control allows.
_keys: dict[str, jwt.PyJWK] = {}
_keys_until = 0.0


class GoogleError(AuthError):
    pass


class GoogleIdentity(BaseModel):
    """The person as Google's verified ID token describes them."""

    sub: str
    email: str
    email_verified: bool
    name: str | None = None


class GoogleClient:
    """OpenID Connect against Google: the authorization URL, the code exchange and the ID token's checks."""

    def __init__(self, client_id: str, client_secret: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._transport = transport

    def authorize_url(self, state: str, code_challenge: str, redirect_uri: str) -> str:
        query = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    async def identity(self, code: str, code_verifier: str, redirect_uri: str) -> GoogleIdentity:
        """Exchanges the code and gives who signed in; GoogleError when Google refuses or the token fails a check."""
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "code_verifier": code_verifier,
                        "redirect_uri": redirect_uri,
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                )
                response.raise_for_status()
                claims = await self._verified_claims(client, response.json()["id_token"])
            return GoogleIdentity.model_validate(claims)
        except (httpx.HTTPError, jwt.PyJWTError, KeyError, ValueError) as exc:
            raise GoogleError("Google did not confirm who signed in.") from exc

    async def _verified_claims(self, client: httpx.AsyncClient, id_token: str) -> dict[str, Any]:
        key = await self._key(client, jwt.get_unverified_header(id_token).get("kid", ""))
        return jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=self._client_id,
            issuer=ISSUERS,
            options={"require": ["exp", "iss", "aud"]},
        )

    async def _key(self, client: httpx.AsyncClient, kid: str) -> jwt.PyJWK:
        global _keys_until
        # An unknown kid after Google rotated its keys refetches them before giving up.
        if kid not in _keys or time.time() >= _keys_until:
            response = await client.get(JWKS_URL)
            response.raise_for_status()
            _keys.clear()
            _keys.update({key["kid"]: jwt.PyJWK(key) for key in response.json()["keys"]})
            max_age = re.search(r"max-age=(\d+)", response.headers.get("cache-control", ""))
            _keys_until = time.time() + (int(max_age.group(1)) if max_age else 0)
        return _keys[kid]
