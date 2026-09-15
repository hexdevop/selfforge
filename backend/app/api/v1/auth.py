from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status

from app.core.config import settings
from app.core.exceptions import InvalidTokenException
from app.dependencies.auth import CurrentActiveUser
from app.dependencies.db import DbSession
from app.dependencies.rate_limit import rate_limit
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth import AuthService, IssuedTokens

router = APIRouter(prefix="/auth", tags=["auth"])

# The refresh token lives only in an httpOnly cookie scoped to the auth routes,
# so page scripts never see it; SameSite=Strict keeps it off cross-site requests.
REFRESH_COOKIE = "refresh_token"
_REFRESH_COOKIE_PATH = f"{settings.API_V1_PREFIX}/auth"

RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _set_refresh_cookie(response: Response, tokens: IssuedTokens) -> TokenResponse:
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path=_REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.ENV in ("staging", "production"),
        samesite="strict",
    )
    return TokenResponse(access_token=tokens.access_token)


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register", limit=10, window_seconds=3600))],
)
async def register(data: UserCreate, session: DbSession) -> UserRead:
    user = await AuthService(session).register(data)
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("login", limit=10, window_seconds=60))],
)
async def login(data: LoginRequest, session: DbSession, response: Response) -> TokenResponse:
    tokens = await AuthService(session).login(data.login, data.password)
    return _set_refresh_cookie(response, tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    session: DbSession, response: Response, refresh_token: RefreshCookie = None
) -> TokenResponse:
    if refresh_token is None:
        raise InvalidTokenException()
    tokens = await AuthService(session).refresh(refresh_token)
    return _set_refresh_cookie(response, tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    session: DbSession, response: Response, refresh_token: RefreshCookie = None
) -> None:
    if refresh_token is not None:
        await AuthService(session).logout(refresh_token)
    response.delete_cookie(REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentActiveUser) -> UserRead:
    return UserRead.model_validate(user)
