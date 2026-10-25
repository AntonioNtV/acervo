from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from acervo.core.errors import (
    AcervoError,
    AuthError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from acervo.schemas.common import ErrorResponse

# Looked up along the MRO, so a subclass with its own code (e.g. `title_taken`) keeps its parent's status.
STATUS_BY_ERROR: dict[type[AcervoError], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    ValidationError: 422,
    AuthError: 401,
    AcervoError: 500,
}


def _status_of(exc: AcervoError) -> int:
    return next(STATUS_BY_ERROR[cls] for cls in type(exc).__mro__ if cls in STATUS_BY_ERROR)


def _response(status: int, body: ErrorResponse) -> JSONResponse:
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


async def _acervo_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AcervoError)
    body = ErrorResponse(error=exc.code, message=exc.message, details=exc.details)
    return _response(_status_of(exc), body)


async def _request_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    body = ErrorResponse(
        error=ValidationError.code,
        message="Request is invalid.",
        details={"errors": jsonable_encoder(exc.errors())},
    )
    return _response(422, body)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AcervoError, _acervo_error)
    app.add_exception_handler(RequestValidationError, _request_validation_error)
