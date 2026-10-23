import hashlib
import hmac
from typing import Literal
from uuid import UUID

LINK_SECONDS = 60

# Signed into the message, so a link made for one kind of download cannot open another.
Purpose = Literal["file", "cover", "export"]


def sign(secret: str, purpose: Purpose, node_id: UUID, version_id: UUID | None, expires: int) -> str:
    """The signature of a download link of one content of a node for `purpose`, valid until `expires` (Unix
    seconds)."""
    message = f"{purpose}:{node_id}:{version_id or ''}:{expires}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify(
    secret: str,
    purpose: Purpose,
    node_id: UUID,
    version_id: UUID | None,
    expires: int,
    signature: str,
    now: float,
) -> bool:
    # Bytes, as compare_digest raises on a str with non-ASCII characters; the signature comes from the URL.
    expected = sign(secret, purpose, node_id, version_id, expires).encode()
    return now < expires and hmac.compare_digest(expected, signature.encode())
