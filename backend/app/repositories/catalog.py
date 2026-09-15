from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import EquipmentItem, Exercise, MovementPattern, Skill

BODYWEIGHT = "none"


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_patterns(self) -> Sequence[MovementPattern]:
        return (await self.session.scalars(select(MovementPattern))).all()

    async def get_pattern(self, code: str) -> MovementPattern | None:
        return await self.session.get(MovementPattern, code)

    async def list_equipment(self) -> Sequence[EquipmentItem]:
        stmt = select(EquipmentItem).order_by(EquipmentItem.category, EquipmentItem.title_ru)
        return (await self.session.scalars(stmt)).all()

    async def list_exercises(
        self,
        pattern: str | None = None,
        equipment: str | None = None,
        difficulty_min: int | None = None,
        difficulty_max: int | None = None,
    ) -> Sequence[Exercise]:
        stmt = select(Exercise).order_by(
            Exercise.pattern_code, Exercise.difficulty_level, Exercise.title_ru
        )
        if pattern is not None:
            stmt = stmt.where(Exercise.pattern_code == pattern)
        if equipment == BODYWEIGHT:
            stmt = stmt.where(Exercise.required_equipment == [])
        elif equipment is not None:
            # JSONB containment is recursive: [["kettlebell", "dumbbell"]] @> [["kettlebell"]].
            stmt = stmt.where(Exercise.required_equipment.contains([[equipment]]))
        if difficulty_min is not None:
            stmt = stmt.where(Exercise.difficulty_level >= difficulty_min)
        if difficulty_max is not None:
            stmt = stmt.where(Exercise.difficulty_level <= difficulty_max)
        return (await self.session.scalars(stmt)).all()

    async def get_exercise(self, slug: str) -> Exercise | None:
        return (await self.session.scalars(select(Exercise).where(Exercise.slug == slug))).first()

    async def list_skills(self) -> Sequence[Skill]:
        return (await self.session.scalars(select(Skill).order_by(Skill.title_ru))).all()
