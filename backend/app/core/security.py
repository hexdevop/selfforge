import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: UUID) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _encode_token(subject, TokenType.ACCESS, expires_at)


def create_refresh_token_pair(subject: UUID) -> tuple[str, str, datetime]:
    """Return (raw_token, token_hash, expires_at) for a new refresh token.

    Only `token_hash` is persisted in the database — the raw value is
    returned to the client once and never stored, so a database leak alone
    cannot be used to impersonate a user.
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_refresh_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return raw_token, token_hash, expires_at


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _encode_token(subject: UUID, token_type: TokenType, expires_at: datetime) -> str:
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type.value,
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }
    token: str = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> UUID | None:
    """Return the user id encoded in an access token, or None if invalid/expired/wrong type."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None

    if payload.get("type") != TokenType.ACCESS.value:
        return None

    subject = payload.get("sub")
    if subject is None:
        return None

    try:
        return UUID(subject)
    except ValueError:
        return None
