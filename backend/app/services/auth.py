from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AlreadyExistsException,
    InvalidCredentialsException,
    InvalidTokenException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token_pair,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.schemas.user import UserCreate


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    async def register(self, data: UserCreate) -> User:
        if await self.users.get_by_email(data.email):
            raise AlreadyExistsException("A user with this email already exists")
        if await self.users.get_by_username(data.username):
            raise AlreadyExistsException("A user with this username already exists")

        user = await self.users.create(
            email=data.email,
            username=data.username,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
        )
        await self.session.commit()
        return user

    async def authenticate(self, login: str, password: str) -> User:
        user = await self.users.get_by_login(login)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsException()
        return user

    async def login(self, login: str, password: str) -> TokenResponse:
        user = await self.authenticate(login, password)
        tokens = await self._issue_tokens(user.id)
        await self.session.commit()
        return tokens

    async def refresh(self, raw_refresh_token: str) -> TokenResponse:
        token_hash = hash_refresh_token(raw_refresh_token)
        stored_token = await self.refresh_tokens.get_by_hash(token_hash)

        if stored_token is None or not stored_token.is_active:
            raise InvalidTokenException("Refresh token is invalid, expired or already used")

        # Rotate: revoke the used token and issue a fresh pair.
        await self.refresh_tokens.revoke(stored_token)
        tokens = await self._issue_tokens(stored_token.user_id)
        await self.session.commit()
        return tokens

    async def logout(self, raw_refresh_token: str) -> None:
        token_hash = hash_refresh_token(raw_refresh_token)
        stored_token = await self.refresh_tokens.get_by_hash(token_hash)
        if stored_token is not None and stored_token.is_active:
            await self.refresh_tokens.revoke(stored_token)
            await self.session.commit()

    async def _issue_tokens(self, user_id: UUID) -> TokenResponse:
        access_token = create_access_token(user_id)
        raw_refresh_token, token_hash, expires_at = create_refresh_token_pair(user_id)

        await self.refresh_tokens.create(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )

        return TokenResponse(access_token=access_token, refresh_token=raw_refresh_token)
