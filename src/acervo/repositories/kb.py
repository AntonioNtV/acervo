from uuid import UUID

from sqlalchemy import func, select

from acervo.db.models.kb import Kb
from acervo.repositories.base import BaseRepository
from acervo.schemas.kb import KbCreate, KbRead, KbUpdate


class KbRepository(BaseRepository[Kb, KbRead, KbCreate, KbUpdate]):
    orm_model = Kb
    read_schema = KbRead

    async def lock(self, kb_id: UUID) -> None:
        """One writer per base until the transaction ends, so checks such as "já existe" hold until the write."""
        await self._session.execute(select(func.pg_advisory_xact_lock(int.from_bytes(kb_id.bytes[:8], signed=True))))
