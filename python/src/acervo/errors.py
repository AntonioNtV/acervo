from typing import Any


class AcervoError(Exception):
    status = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def to_response(self) -> dict[str, Any]:
        return {"error": type(self).__name__, "message": self.message}


class ValidationError(AcervoError):
    status = 400


class NotFoundError(AcervoError):
    status = 404


class ConflictError(AcervoError):
    """A clash the person can act on: a taken name, a duplicate file, a page that changed since it was opened."""

    status = 409

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.detail = detail

    def to_response(self) -> dict[str, Any]:
        return {**super().to_response(), "detail": self.detail}


class ForbiddenOperation(AcervoError):
    status = 422


class DecisionUnavailable(AcervoError):
    status = 503
