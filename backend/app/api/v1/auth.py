from fastapi import APIRouter, status

from app.dependencies.auth import CurrentActiveUser
from app.dependencies.db import DbSession
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, session: DbSession) -> UserRead:
    user = await AuthService(session).register(data)
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, session: DbSession) -> TokenResponse:
    return await AuthService(session).login(data.login, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, session: DbSession) -> TokenResponse:
    return await AuthService(session).refresh(data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest, session: DbSession) -> None:
    await AuthService(session).logout(data.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentActiveUser) -> UserRead:
    return UserRead.model_validate(user)
