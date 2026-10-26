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


class LastWayIn(ConflictError):
    """The account would be left with no way to sign in: no password, no Google and no other passkey."""

    code = "last_way_in"


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


class ReauthenticationRequired(AuthError):
    """A sensitive change, with no password or passkey asked in the last 10 minutes; 403, the session stays."""

    code = "reauthentication_required"


class ForbiddenError(AcervoError):
    """The person's role does not allow it."""

    code = "forbidden"


class TwoFactorRequired(ForbiddenError):
    """The organization requires a passkey or two-step verification the account does not have yet."""

    code = "two_factor_required"


class TooManyAttempts(AcervoError):
    code = "too_many_attempts"
