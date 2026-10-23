from typing import Any
from uuid import UUID

from sqlalchemy import Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from acervo.db.base import Base, TimestampMixin, UUIDPkMixin


class DecisionLog(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "decision_log"

    run_id: Mapped[UUID] = mapped_column(index=True)
    step: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(Text)
    options: Mapped[list[Any]]
    probs: Mapped[list[Any]]
    threshold: Mapped[float | None] = mapped_column(Float)
    action: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int]
    cached: Mapped[bool] = mapped_column(server_default="false", default=False)
    message_id: Mapped[UUID | None] = mapped_column(ForeignKey("message.id"), index=True)
