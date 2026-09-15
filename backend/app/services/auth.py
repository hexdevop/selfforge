from dataclasses import dataclass
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
from app.schemas.user import UserCreate


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    async def register(self, data: UserCreate) -> User:
        if await self.users.get_by_email(data.email):
            raise AlreadyExistsException(
                "Этот email уже зарегистрирован", {"email": "Этот email уже занят"}
            )
        if await self.users.get_by_username(data.username):
            raise AlreadyExistsException(
                "Это имя пользователя уже занято", {"username": "Это имя уже занято"}
            )

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

    async def login(self, login: str, password: str) -> IssuedTokens:
        user = await self.authenticate(login, password)
        tokens = await self._issue_tokens(user.id)
        await self.session.commit()
        return tokens

    async def refresh(self, raw_refresh_token: str) -> IssuedTokens:
        token_hash = hash_refresh_token(raw_refresh_token)
        stored_token = await self.refresh_tokens.get_by_hash(token_hash)

        if stored_token is None or not stored_token.is_active:
            raise InvalidTokenException()

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

    async def _issue_tokens(self, user_id: UUID) -> IssuedTokens:
        access_token = create_access_token(user_id)
        raw_refresh_token, token_hash, expires_at = create_refresh_token_pair(user_id)

        await self.refresh_tokens.create(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )

        return IssuedTokens(access_token=access_token, refresh_token=raw_refresh_token)
