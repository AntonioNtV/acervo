import base64
import hashlib
import hmac
import json
from typing import Any, Literal
from uuid import UUID

LINK_SECONDS = 60

# Signed into the message, so a link made for one kind of download cannot open another.
Purpose = Literal["file", "cover", "export", "attachment"]


def sign(secret: str, purpose: Purpose, node_id: UUID, version_id: UUID | None, session_id: UUID, expires: int) -> str:
    """The signature of a download link of one content of a node for `purpose`, minted in session `session_id` and
    valid until `expires` (Unix seconds)."""
    message = f"{purpose}:{node_id}:{version_id or ''}:{session_id}:{expires}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify(
    secret: str,
    purpose: Purpose,
    node_id: UUID,
    version_id: UUID | None,
    session_id: UUID,
    expires: int,
    signature: str,
    now: float,
) -> bool:
    # Bytes, as compare_digest raises on a str with non-ASCII characters; the signature comes from the URL.
    expected = sign(secret, purpose, node_id, version_id, session_id, expires).encode()
    return now < expires and hmac.compare_digest(expected, signature.encode())


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def seal(secret: str, purpose: str, expires: int, **values: str) -> str:
    """`values` signed with `secret` for `purpose`, readable until `expires` (Unix seconds)."""
    body = _b64(json.dumps({**values, "purpose": purpose, "exp": expires}).encode())
    return f"{body}.{hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()}"


def unseal(secret: str, purpose: str, sealed: str | None, now: float) -> dict[str, Any] | None:
    """What `seal` signed for `purpose`; None when forged, expired or made for another purpose."""
    body, _, signature = (sealed or "").rpartition(".")
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not body or not hmac.compare_digest(expected.encode(), signature.encode()):
        return None
    values: dict[str, Any] = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    if values["purpose"] != purpose or values["exp"] <= now:
        return None
    return values
