"""`arq acervo.worker.settings.WorkerSettings`: the process that runs a message's work out of the request."""

from typing import Any, ClassVar

from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from acervo.core.settings import get_settings
from acervo.model_clients.chat_agent import ChatAgent
from acervo.model_clients.factory import build_decider, build_writer
from acervo.repositories.uow import UnitOfWork
from acervo.services.chat_service import fail_interrupted
from acervo.services.events import ArqJobQueue, RedisEventBus
from acervo.services.storage import Storage
from acervo.worker.jobs import handle_message, refresh_descriptions


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    # The layers keep `db` out of the worker, so the engine is built here as `db/session.py` builds the API's.
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with UnitOfWork(session_factory) as uow:
        await fail_interrupted(uow, settings.job_timeout_seconds)
    ctx.update(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        storage=Storage(settings),
        events=RedisEventBus(settings.redis_url),
        jobs=ArqJobQueue(settings.redis_url),
        decider=build_decider(settings),
        writer=build_writer(settings),
        chat=ChatAgent(settings.llm_roles.chat),
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["jobs"].close()
    await ctx["events"].close()
    await ctx["engine"].dispose()


class WorkerSettings:
    functions: ClassVar[list[Any]] = [handle_message, refresh_descriptions]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    job_timeout = get_settings().job_timeout_seconds
    # A retry would make the message's proposals again.
    max_tries = 1
