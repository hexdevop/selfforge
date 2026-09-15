from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.decorator import cached, invalidate_prefix
from app.core.exceptions import AlreadyExistsException, NotFoundException
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.pagination import Page, PageParams
from app.schemas.user import UserRead, UserUpdate

_CACHE_PREFIX = "user"


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def get(self, user_id: UUID) -> User:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundException("User not found")
        return user

    @cached(key_prefix=_CACHE_PREFIX)
    async def get_cached(self, user_id: UUID) -> dict[str, Any]:
        """Same as `get`, but returns a cached JSON-safe dict.

        Example of wiring a service method through the Redis cache decorator —
        cache the *serialized* response, not the ORM object, and invalidate
        it whenever the underlying row changes (see `update`/`delete` below).
        """
        user = await self.get(user_id)
        return UserRead.model_validate(user).model_dump(mode="json")

    async def list(self, pagination: PageParams, is_active: bool | None = None) -> Page[User]:
        filters = {"is_active": is_active} if is_active is not None else {}
        order_by = User.created_at.desc()
        return await self.users.list(filters=filters, pagination=pagination, order_by=order_by)

    async def update(self, user_id: UUID, data: UserUpdate) -> User:
        user = await self.get(user_id)
        values = data.model_dump(exclude_unset=True, exclude={"password"})

        if data.email and data.email != user.email and await self.users.get_by_email(data.email):
            raise AlreadyExistsException("A user with this email already exists")
        if (
            data.username
            and data.username != user.username
            and await self.users.get_by_username(data.username)
        ):
            raise AlreadyExistsException("A user with this username already exists")

        if data.password:
            values["hashed_password"] = hash_password(data.password)

        user = await self.users.update(user, **values)
        await self.session.commit()
        await invalidate_prefix(_CACHE_PREFIX)
        return user

    async def delete(self, user_id: UUID) -> None:
        user = await self.get(user_id)
        await self.users.delete(user)
        await self.session.commit()
        await invalidate_prefix(_CACHE_PREFIX)
