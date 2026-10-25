from typing import Any, ClassVar


class AcervoError(Exception):
    """Base of every error Acervo raises on purpose; `code` is the `ErrorResponse.error` it maps to."""

    code: ClassVar[str] = "internal"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AcervoError):
    code = "not_found"


class ConflictError(AcervoError):
    """A clash the person can act on; the subclasses are the ones the screens tell apart."""

    code = "conflict"


class TitleTaken(ConflictError):
    code = "title_taken"


class Duplicate(ConflictError):
    code = "duplicate"


class StalePage(ConflictError):
    code = "stale_page"


class SameFile(ConflictError):
    code = "same_file"


class ValidationError(AcervoError):
    code = "validation"


class AuthError(AcervoError):
    code = "unauthorized"
