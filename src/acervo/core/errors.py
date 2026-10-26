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


class EmailTaken(ConflictError):
    code = "email_taken"


class LastOwner(ConflictError):
    """The organization would be left without an Owner."""

    code = "last_owner"


class AlreadyMember(ConflictError):
    code = "already_member"


class ValidationError(AcervoError):
    code = "validation"


class CodeInvalid(ValidationError):
    """A code or link that is wrong, expired, used or out of tries; the person is not told which."""

    code = "code_invalid"


class InviteMismatch(ValidationError):
    """An invite opened by an account of another email."""

    code = "invite_email_mismatch"


class AuthError(AcervoError):
    code = "unauthorized"


class InvalidCredentials(AuthError):
    """A wrong email or a wrong password, with the same body for both."""

    code = "invalid_credentials"


class EmailNotVerified(AuthError):
    code = "email_not_verified"


class ForbiddenError(AcervoError):
    """The person's role does not allow it."""

    code = "forbidden"


class TooManyAttempts(AcervoError):
    code = "too_many_attempts"
