import uuid

import uuid6


def uuid7() -> uuid.UUID:
    """Time-ordered UUID v7, so primary keys sort by creation."""
    return uuid.UUID(int=uuid6.uuid7().int)
