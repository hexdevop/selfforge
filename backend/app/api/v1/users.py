from typing import Any
from uuid import UUID

from fastapi import APIRouter, status

from app.core.exceptions import PermissionDeniedException
from app.dependencies.auth import CurrentActiveUser, CurrentSuperuser
from app.dependencies.db import DbSession
from app.dependencies.pagination import Pagination
from app.schemas.pagination import Page
from app.schemas.user import UserRead, UserUpdate
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=Page[UserRead])
async def list_users(
    session: DbSession, pagination: Pagination, _: CurrentSuperuser
) -> Page[UserRead]:
    page = await UserService(session).list(pagination)
    return Page[UserRead].create(
        items=[UserRead.model_validate(user) for user in page.items],
        total=page.total,
        params=pagination,
    )


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: UUID, session: DbSession, _: CurrentActiveUser) -> dict[str, Any]:
    return await UserService(session).get_cached(user_id)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID, data: UserUpdate, session: DbSession, current_user: CurrentActiveUser
) -> UserRead:
    if current_user.id != user_id and not current_user.is_superuser:
        raise PermissionDeniedException("You can only update your own profile")

    user = await UserService(session).update(user_id, data)
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: UUID, session: DbSession, _: CurrentSuperuser) -> None:
    await UserService(session).delete(user_id)
