import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.repositories.filters import apply_filters
from app.schemas.pagination import Page, PageParams


class BaseRepository[ModelType: Base]:
    """Generic async CRUD repository with dict-based filtering and pagination.

    Concrete repositories (e.g. `UserRepository`) subclass this and set
    `model`, adding only the queries that don't fit the generic shape.
    """

    model: type[ModelType]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: uuid.UUID) -> ModelType | None:
        return await self.session.get(self.model, id)

    async def get_by(self, **filters: Any) -> ModelType | None:
        stmt = apply_filters(select(self.model), self.model, filters)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        pagination: PageParams | None = None,
        order_by: Any = None,
    ) -> Page[ModelType]:
        pagination = pagination or PageParams()
        stmt = apply_filters(select(self.model), self.model, filters or {})

        total = await self._count(stmt)

        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.offset(pagination.offset).limit(pagination.limit)

        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return Page.create(items=items, total=total, params=pagination)

    async def _count(self, stmt: Any) -> int:
        count_stmt = select(func.count()).select_from(stmt.subquery())
        result = await self.session.execute(count_stmt)
        return result.scalar_one()

    async def create(self, **values: Any) -> ModelType:
        obj = self.model(**values)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, obj: ModelType, **values: Any) -> ModelType:
        for field, value in values.items():
            setattr(obj, field, value)
        await self.session.flush()
        return obj

    async def delete(self, obj: ModelType) -> None:
        await self.session.delete(obj)
        await self.session.flush()
