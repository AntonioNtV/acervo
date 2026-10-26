from uuid import UUID

from acervo.db.models.email_code import EmailCode
from acervo.repositories.base import BaseRepository
from acervo.schemas.account import CodePurpose, EmailCodeCreate, EmailCodeRecord, EmailCodeUpdate


class EmailCodeRepository(BaseRepository[EmailCode, EmailCodeRecord, EmailCodeCreate, EmailCodeUpdate]):
    orm_model = EmailCode
    read_schema = EmailCodeRecord

    async def live(self, account_id: UUID, purpose: CodePurpose) -> EmailCodeRecord | None:
        """The one code not yet used, expired or not."""
        query = self._select().where(
            EmailCode.account_id == account_id, EmailCode.purpose == purpose, EmailCode.used_at.is_(None)
        )
        code = await self._session.scalar(query)
        return None if code is None else self._to_read(code)
