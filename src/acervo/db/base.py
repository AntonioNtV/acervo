from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from acervo.core.ids import uuid7

# Migration 0001 named every index and constraint with this convention; the stored names must not change.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(AsyncAttrs, DeclarativeBase):
    metadata = MetaData(schema="acervo", naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: DateTime(timezone=True), dict[str, Any]: JSONB, list[Any]: JSONB}


class UUIDPkMixin:
    # Rows written before uuid7 carry the database's uuid4, which the server default still gives.
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7, server_default=func.gen_random_uuid())


class TimestampMixin:
    # Fetch server-set timestamps with RETURNING on insert and update: a lazy refresh would fail under asyncio.
    __mapper_args__: Any = {"eager_defaults": True}

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
