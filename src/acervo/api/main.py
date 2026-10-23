from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from acervo.api.errors import register_error_handlers
from acervo.api.routers import covers, exports, favorites, files, health, kbs, nodes, pages, trash
from acervo.core.settings import Settings, get_settings
from acervo.db.session import create_engine, create_session_factory
from acervo.services.storage import Storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_engine(app.state.settings)
    app.state.session_factory = create_session_factory(engine)
    app.state.storage = Storage(app.state.settings)
    try:
        yield
    finally:
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Factory used by uvicorn and by the tests."""
    app = FastAPI(title="Acervo", lifespan=lifespan)
    app.state.settings = settings or get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app.state.settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Range", "Accept-Ranges", "Content-Disposition"],
    )
    register_error_handlers(app)
    for module in (health, kbs, nodes, trash, files, pages, favorites, covers, exports):
        app.include_router(module.router)
    return app


app = create_app()
