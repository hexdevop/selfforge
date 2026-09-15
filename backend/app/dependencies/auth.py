from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.exceptions import (
    InactiveUserException,
    InvalidTokenException,
    PermissionDeniedException,
)
from app.core.security import decode_access_token
from app.dependencies.db import DbSession
from app.models.user import User
from app.repositories.user import UserRepository

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    session: DbSession,
    token: Annotated[str | None, Depends(_oauth2_scheme)],
) -> User:
    if token is None:
        raise InvalidTokenException("Нужно войти")

    user_id = decode_access_token(token)
    if user_id is None:
        raise InvalidTokenException()

    user = await UserRepository(session).get(user_id)
    if user is None:
        raise InvalidTokenException()

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_active_user(user: CurrentUser) -> User:
    if not user.is_active:
        raise InactiveUserException()
    return user


CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]


async def get_current_superuser(user: CurrentActiveUser) -> User:
    if not user.is_superuser:
        raise PermissionDeniedException()
    return user


CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]
