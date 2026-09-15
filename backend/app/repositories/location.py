import uuid
from collections.abc import Sequence

from sqlalchemy import select, update

from app.models.location import Location
from app.repositories.base import BaseRepository


class LocationRepository(BaseRepository[Location]):
    model = Location

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[Location]:
        stmt = (
            select(Location)
            .where(Location.user_id == user_id)
            .order_by(Location.is_default.desc(), Location.created_at)
        )
        return (await self.session.scalars(stmt)).all()

    async def get_for_user(self, location_id: uuid.UUID, user_id: uuid.UUID) -> Location | None:
        stmt = select(Location).where(Location.id == location_id, Location.user_id == user_id)
        return (await self.session.scalars(stmt)).first()

    async def clear_default(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Location).where(Location.user_id == user_id).values(is_default=False)
        )
