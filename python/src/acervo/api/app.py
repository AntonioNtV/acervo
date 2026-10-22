from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from acervo.api.routes import router
from acervo.config import Settings
from acervo.errors import AcervoError

app = FastAPI(title="Acervo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=Settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(AcervoError)
async def acervo_error(_: Request, error: AcervoError) -> JSONResponse:
    return JSONResponse(status_code=error.status, content=error.to_response())
