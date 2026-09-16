import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select

from app.models.body import BodyMetric, ProgressPhoto, SkillProgress
from app.repositories.base import BaseRepository


class BodyMetricRepository(BaseRepository[BodyMetric]):
    model = BodyMetric

    async def for_user(
        self,
        user_id: uuid.UUID,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Sequence[BodyMetric]:
        stmt = select(BodyMetric).where(BodyMetric.user_id == user_id)
        if since is not None:
            stmt = stmt.where(BodyMetric.measured_at >= since)
        if until is not None:
            stmt = stmt.where(BodyMetric.measured_at <= until)
        return (await self.session.scalars(stmt.order_by(BodyMetric.measured_at.desc()))).all()


class ProgressPhotoRepository(BaseRepository[ProgressPhoto]):
    model = ProgressPhoto

    async def for_user(self, user_id: uuid.UUID) -> Sequence[ProgressPhoto]:
        stmt = (
            select(ProgressPhoto)
            .where(ProgressPhoto.user_id == user_id)
            .order_by(ProgressPhoto.taken_at.desc())
        )
        return (await self.session.scalars(stmt)).all()


class SkillProgressRepository(BaseRepository[SkillProgress]):
    model = SkillProgress

    async def for_user(self, user_id: uuid.UUID) -> Sequence[SkillProgress]:
        stmt = select(SkillProgress).where(SkillProgress.user_id == user_id)
        return (await self.session.scalars(stmt)).all()
