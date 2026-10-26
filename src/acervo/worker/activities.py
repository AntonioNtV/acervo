from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from temporalio import activity

from acervo.repositories.uow import UnitOfWork
from acervo.services.digest_service import DigestService
from acervo.services.mailer import Mailer


class DigestActivities:
    """Each activity is one unit of work around DigestService."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], mailer: Mailer) -> None:
        self._session_factory = session_factory
        self._mailer = mailer

    @activity.defn(name="digest_due")
    async def due(self, now: datetime) -> list[UUID]:
        async with UnitOfWork(self._session_factory) as uow:
            return await DigestService(uow, self._mailer).due(now)

    @activity.defn(name="digest_send")
    async def send(self, account_id: UUID, now: datetime) -> None:
        async with UnitOfWork(self._session_factory) as uow:
            await DigestService(uow, self._mailer).send(account_id, now)
