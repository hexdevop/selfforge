import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.models.profile import PatternLevel, Profile
from app.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[Profile]):
    model = Profile


class PatternLevelRepository(BaseRepository[PatternLevel]):
    model = PatternLevel

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[PatternLevel]:
        # upsert() bypasses the ORM, so refresh whatever the session already holds.
        stmt = (
            select(PatternLevel)
            .where(PatternLevel.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        return (await self.session.scalars(stmt)).all()

    async def upsert(self, user_id: uuid.UUID, rows: list[dict[str, Any]]) -> None:
        stmt = insert(PatternLevel).values([{**row, "user_id": user_id} for row in rows])
        await self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=["user_id", "pattern_code"],
                set_={
                    "current_exercise_slug": stmt.excluded.current_exercise_slug,
                    "estimated_level": stmt.excluded.estimated_level,
                    "assessment_source": stmt.excluded.assessment_source,
                    "updated_at": func.now(),
                },
            )
        )
