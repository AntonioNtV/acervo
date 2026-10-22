from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from acervo.api.routes import router
from acervo.config import Settings
from acervo.errors import AcervoError, ValidationError

app = FastAPI(title="Acervo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=Settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Disposition"],
)
app.include_router(router)


@app.exception_handler(AcervoError)
async def acervo_error(_: Request, error: AcervoError) -> JSONResponse:
    return JSONResponse(status_code=error.status, content=error.to_response())


@app.exception_handler(RequestValidationError)
async def request_invalid(_: Request, error: RequestValidationError) -> JSONResponse:
    message = "; ".join(f"{'.'.join(map(str, item['loc']))}: {item['msg']}" for item in error.errors())
    invalid = ValidationError(message)
    return JSONResponse(status_code=invalid.status, content=invalid.to_response())
