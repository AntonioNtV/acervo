from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import delete, func, select

from acervo.db.models.login_failure import LoginFailure
from acervo.repositories.base import BaseRepository
from acervo.schemas.account import LoginFailureCreate, LoginFailureRecord


class LoginFailureRepository(BaseRepository[LoginFailure, LoginFailureRecord, LoginFailureCreate, BaseModel]):
    orm_model = LoginFailure
    read_schema = LoginFailureRecord

    async def count_since(self, email_lower: str, since: datetime) -> int:
        query = select(func.count()).where(LoginFailure.email_lower == email_lower, LoginFailure.created_at >= since)
        return await self._session.scalar(query) or 0

    async def clear(self, email_lower: str) -> None:
        await self._session.execute(delete(LoginFailure).where(LoginFailure.email_lower == email_lower))
