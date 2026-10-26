from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import delete, func, select

from acervo.db.models.login_failure import LoginFailure
from acervo.repositories.base import BaseRepository
from acervo.schemas.account import LoginFailureCreate, LoginFailureRecord


class LoginFailureRepository(BaseRepository[LoginFailure, LoginFailureRecord, LoginFailureCreate, BaseModel]):
    orm_model = LoginFailure
    read_schema = LoginFailureRecord

    async def lock(self, email_lower: str) -> None:
        """Holds the email's sign-ins one at a time until the transaction ends, so none counts failures too early."""
        await self._session.execute(select(func.pg_advisory_xact_lock(func.hashtext(email_lower))))

    async def latest(self, email_lower: str, limit: int) -> list[datetime]:
        """When the last `limit` failures happened, newest first."""
        query = (
            select(LoginFailure.created_at)
            .where(LoginFailure.email_lower == email_lower)
            .order_by(LoginFailure.created_at.desc())
            .limit(limit)
        )
        return list(await self._session.scalars(query))

    async def clear(self, email_lower: str, before: datetime | None = None) -> None:
        """Deletes the email's failures, only those older than `before` when given."""
        query = delete(LoginFailure).where(LoginFailure.email_lower == email_lower)
        if before is not None:
            query = query.where(LoginFailure.created_at < before)
        await self._session.execute(query)
