from datetime import UTC, datetime
from uuid import UUID

from app.models.refresh_token import RefreshToken
from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return await self.get_by(token_hash=token_hash)

    async def revoke(self, token: RefreshToken) -> None:
        await self.update(token, revoked_at=datetime.now(UTC))

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        tokens = await self.list(filters={"user_id": user_id, "revoked_at__is_null": True})
        for token in tokens.items:
            token.revoked_at = datetime.now(UTC)
        await self.session.flush()
