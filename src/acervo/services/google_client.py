import base64
import hashlib
import hmac
import json
import re
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

from acervo.core.errors import AuthError

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")
TIMEOUT_SECONDS = 10
# DER prefix of a SHA-256 DigestInfo, what an RS256 signature wraps the digest in (RFC 8017, 9.2).
SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")

# Google's signing keys by `kid`, kept as long as Google's Cache-Control allows.
_keys: dict[str, dict[str, str]] = {}
_keys_until = 0.0


class GoogleError(AuthError):
    pass


class GoogleIdentity(BaseModel):
    """The person as Google's verified ID token describes them."""

    sub: str
    email: str
    email_verified: bool
    name: str | None = None


def _b64decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def _rs256_valid(signing_input: bytes, signature: bytes, key: dict[str, str]) -> bool:
    """RSASSA-PKCS1-v1_5 with SHA-256, by rebuilding the expected padded block and comparing it whole."""
    n = int.from_bytes(_b64decode(key["n"]), "big")
    e = int.from_bytes(_b64decode(key["e"]), "big")
    size = (n.bit_length() + 7) // 8
    s = int.from_bytes(signature, "big")
    if len(signature) != size or s >= n:
        return False
    digest_info = SHA256_DIGEST_INFO + hashlib.sha256(signing_input).digest()
    expected = b"\x00\x01" + b"\xff" * (size - 3 - len(digest_info)) + b"\x00" + digest_info
    return hmac.compare_digest(pow(s, e, n).to_bytes(size, "big"), expected)


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
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise GoogleError("Google did not confirm who signed in.") from exc

    async def _verified_claims(self, client: httpx.AsyncClient, id_token: str) -> dict[str, Any]:
        header_part, payload_part, signature_part = id_token.split(".")
        header = json.loads(_b64decode(header_part))
        if header.get("alg") != "RS256":
            raise ValueError("unexpected algorithm")
        key = await self._key(client, header.get("kid", ""))
        if not _rs256_valid(f"{header_part}.{payload_part}".encode(), _b64decode(signature_part), key):
            raise ValueError("bad signature")
        claims: dict[str, Any] = json.loads(_b64decode(payload_part))
        if claims.get("iss") not in ISSUERS or claims.get("aud") != self._client_id:
            raise ValueError("token not meant for this client")
        if not isinstance(claims.get("exp"), int) or claims["exp"] <= time.time():
            raise ValueError("token expired")
        return claims

    async def _key(self, client: httpx.AsyncClient, kid: str) -> dict[str, str]:
        global _keys_until
        # An unknown kid after Google rotated its keys refetches them before giving up.
        if kid not in _keys or time.time() >= _keys_until:
            response = await client.get(JWKS_URL)
            response.raise_for_status()
            _keys.clear()
            _keys.update({key["kid"]: key for key in response.json()["keys"]})
            max_age = re.search(r"max-age=(\d+)", response.headers.get("cache-control", ""))
            _keys_until = time.time() + (int(max_age.group(1)) if max_age else 0)
        return _keys[kid]
