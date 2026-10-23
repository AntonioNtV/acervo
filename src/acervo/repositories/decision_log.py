from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select

from acervo.db.models.decision_log import DecisionLog
from acervo.repositories.base import BaseRepository
from acervo.schemas.proposal import DecisionLogCreate, DecisionLogRead


class DecisionLogRepository(BaseRepository[DecisionLog, DecisionLogRead, DecisionLogCreate, BaseModel]):
    """Decisions are written once and never changed."""

    orm_model = DecisionLog
    read_schema = DecisionLogRead

    async def of_run(self, run_id: UUID) -> list[DecisionLogRead]:
        """The run's decisions in the order they were asked."""
        query = select(DecisionLog).where(DecisionLog.run_id == run_id).order_by(DecisionLog.created_at, DecisionLog.id)
        return [self._to_read(decision) for decision in await self._session.scalars(query)]
