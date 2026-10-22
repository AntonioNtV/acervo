import hashlib
import hmac
from uuid import UUID

LINK_SECONDS = 60


def sign(secret: str, node_id: UUID, version_id: UUID | None, expires: int) -> str:
    """The signature of a download link of one content of a file, valid until `expires` (Unix seconds)."""
    message = f"{node_id}:{version_id or ''}:{expires}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify(secret: str, node_id: UUID, version_id: UUID | None, expires: int, signature: str, now: float) -> bool:
    return now < expires and hmac.compare_digest(sign(secret, node_id, version_id, expires), signature)
