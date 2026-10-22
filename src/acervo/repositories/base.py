import builtins
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Select, func, inspect, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import ConflictError, NotFoundError, ValidationError
from acervo.db.base import Base
from acervo.schemas.common import PageParams, Paginated

UNIQUE_VIOLATION = "23505"


class BaseRepository[OrmT: Base, ReadT: BaseModel, CreateT: BaseModel, UpdateT: BaseModel]:
    """CRUD over one table, in and out as Pydantic models. Never commits: the UnitOfWork does."""

    orm_model: ClassVar[type[Base]]
    read_schema: ClassVar[type[BaseModel]]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: UUID) -> ReadT:
        return self._to_read(await self._get_orm(id))

    async def get_or_none(self, id: UUID) -> ReadT | None:
        obj = await self._session.get(self.orm_model, id)
        return None if obj is None else self._to_read(obj)  # type: ignore[arg-type]

    async def get_by(self, **filters: Any) -> ReadT | None:
        obj = await self._session.scalar(self._apply_filters(self._select(), filters).limit(1))
        return None if obj is None else self._to_read(obj)

    async def list(
        self,
        *,
        filters: Mapping[str, Any] | None = None,
        order_by: Sequence[str] = ("-created_at", "-id"),
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReadT]:
        stmt = self._apply_order(self._apply_filters(self._select(), filters or {}), order_by)
        result = await self._session.scalars(stmt.limit(limit).offset(offset))
        return [self._to_read(obj) for obj in result]

    async def paginate(self, params: PageParams, filters: Mapping[str, Any] | None = None) -> Paginated[ReadT]:
        items = await self.list(filters=filters, limit=params.limit, offset=params.offset)
        # The concrete Paginated[XRead] class, so the items serialize with their own fields.
        page_type: type[Paginated[ReadT]] = Paginated[self.read_schema]  # type: ignore[name-defined]
        return page_type(items=items, total=await self.count(filters), limit=params.limit, offset=params.offset)

    async def count(self, filters: Mapping[str, Any] | None = None) -> int:
        stmt = self._apply_filters(select(func.count()).select_from(self.orm_model), filters or {})
        return await self._session.scalar(stmt) or 0

    async def exists(self, **filters: Any) -> bool:
        stmt = self._apply_filters(select(literal(1)).select_from(self.orm_model), filters).limit(1)
        return await self._session.scalar(stmt) is not None

    async def create(self, data: CreateT, **extra: Any) -> ReadT:
        obj = self._new(data, extra)
        self._session.add(obj)
        await self._flush()
        return self._to_read(obj)

    async def create_many(self, items: Sequence[CreateT]) -> builtins.list[ReadT]:
        objs = [self._new(data, {}) for data in items]
        self._session.add_all(objs)
        await self._flush()
        return [self._to_read(obj) for obj in objs]

    async def update(self, id: UUID, data: UpdateT) -> ReadT:
        obj = await self._get_orm(id)
        if not data.model_fields_set:
            return self._to_read(obj)
        for name in data.model_fields_set:
            setattr(obj, name, getattr(data, name))
        await self._flush()
        return self._to_read(obj)

    async def delete(self, id: UUID) -> None:
        await self._session.delete(await self._get_orm(id))
        await self._flush()

    def _select(self) -> Select[OrmT]:
        return select(self.orm_model)

    async def _get_orm(self, id: UUID) -> OrmT:
        obj = await self._session.get(self.orm_model, id)
        if obj is None:
            raise NotFoundError(f"{self.orm_model.__tablename__} {id} not found", {"id": str(id)})
        return obj  # type: ignore[return-value]

    def _apply_filters[S: Select[Any]](self, stmt: S, filters: Mapping[str, Any]) -> S:
        for name, value in filters.items():
            stmt = stmt.where(self._column(name) == value)
        return stmt

    def _apply_order[S: Select[Any]](self, stmt: S, order_by: Sequence[str]) -> S:
        for key in order_by:
            column = self._column(key.removeprefix("-"))
            stmt = stmt.order_by(column.desc() if key.startswith("-") else column.asc())
        return stmt

    def _column(self, name: str) -> Any:
        columns = inspect(self.orm_model).columns
        if name not in columns:
            raise ValidationError(f"unknown column {name!r} on {self.orm_model.__tablename__}", {"column": name})
        return columns[name]

    def _new(self, data: CreateT, extra: Mapping[str, Any]) -> OrmT:
        return self.orm_model(**dict(data), **extra)  # type: ignore[return-value]

    async def _flush(self) -> None:
        try:
            await self._session.flush()
        except IntegrityError as exc:
            cause = exc.orig.__cause__ if exc.orig is not None else None
            if getattr(cause, "sqlstate", None) != UNIQUE_VIOLATION:
                raise
            constraint = getattr(cause, "constraint_name", None)
            raise ConflictError(f"violates unique constraint {constraint}", {"constraint": constraint}) from exc

    def _to_read(self, obj: OrmT) -> ReadT:
        return self.read_schema.model_validate(obj, from_attributes=True)  # type: ignore[return-value]
