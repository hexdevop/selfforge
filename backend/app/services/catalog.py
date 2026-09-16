from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.decorator import cached
from app.core.exceptions import NotFoundException
from app.engine.types import CatalogExercise, is_timed
from app.models.catalog import Exercise
from app.repositories.catalog import CatalogRepository
from app.schemas.catalog import (
    EquipmentRead,
    ExerciseRead,
    ExerciseSummary,
    LadderRead,
    PatternCode,
    PatternRead,
    SkillRead,
)

# The catalog changes only when the seed runs; the seed drops this prefix.
CACHE_PREFIX = "catalog"
_TTL = 24 * 3600

_PATTERN_ORDER = list(PatternCode)


def to_engine_exercise(e: Exercise) -> CatalogExercise:
    return CatalogExercise(
        slug=e.slug,
        pattern=e.pattern_code,
        level=e.difficulty_level,
        title=e.title_ru,
        timed=is_timed(e.pattern_code, e.progression_criteria),
        bodyweight_share=e.bodyweight_share,
        required_equipment=tuple(tuple(group) for group in e.required_equipment),
        requires_pair=e.requires_pair,
        is_unilateral=e.is_unilateral,
        is_quiet=e.is_quiet,
        needs_floor_space=e.needs_floor_space,
        needs_ceiling_height=e.needs_ceiling_height,
        lies_on_floor=e.lies_on_floor,
        contraindicated_for=frozenset(e.contraindicated_for),
        prev_slug=e.prev_slug,
        next_slug=e.next_slug,
    )


class CatalogService:
    """Read-only reference data. Methods return JSON-ready dicts so they can be cached."""

    def __init__(self, session: AsyncSession) -> None:
        self.repo = CatalogRepository(session)

    async def engine_exercises(self) -> list[CatalogExercise]:
        return [to_engine_exercise(e) for e in await self.repo.list_exercises()]

    @cached(key_prefix=f"{CACHE_PREFIX}:patterns", ttl=_TTL)
    async def list_patterns(self) -> list[dict[str, Any]]:
        patterns = [PatternRead.model_validate(p) for p in await self.repo.list_patterns()]
        patterns.sort(key=lambda p: _PATTERN_ORDER.index(p.code))
        return [p.model_dump(mode="json") for p in patterns]

    @cached(key_prefix=f"{CACHE_PREFIX}:ladder", ttl=_TTL)
    async def ladder(self, code: str) -> dict[str, Any]:
        pattern = await self.repo.get_pattern(code)
        if pattern is None:
            raise NotFoundException("Такого паттерна движения нет")
        exercises = await self.repo.list_exercises(pattern=code)
        ladder = LadderRead(
            pattern=PatternRead.model_validate(pattern),
            exercises=[ExerciseSummary.model_validate(e) for e in exercises],
        )
        return ladder.model_dump(mode="json")

    @cached(key_prefix=f"{CACHE_PREFIX}:equipment", ttl=_TTL)
    async def list_equipment(self) -> list[dict[str, Any]]:
        items = await self.repo.list_equipment()
        return [EquipmentRead.model_validate(e).model_dump(mode="json") for e in items]

    @cached(key_prefix=f"{CACHE_PREFIX}:exercises", ttl=_TTL)
    async def list_exercises(
        self,
        pattern: str | None = None,
        equipment: str | None = None,
        difficulty_min: int | None = None,
        difficulty_max: int | None = None,
    ) -> list[dict[str, Any]]:
        exercises = await self.repo.list_exercises(
            pattern, equipment, difficulty_min, difficulty_max
        )
        return [ExerciseSummary.model_validate(e).model_dump(mode="json") for e in exercises]

    @cached(key_prefix=f"{CACHE_PREFIX}:exercise", ttl=_TTL)
    async def get_exercise(self, slug: str) -> dict[str, Any]:
        exercise = await self.repo.get_exercise(slug)
        if exercise is None:
            raise NotFoundException("Такого упражнения нет в справочнике")
        return ExerciseRead.model_validate(exercise).model_dump(mode="json")

    @cached(key_prefix=f"{CACHE_PREFIX}:skills", ttl=_TTL)
    async def list_skills(self) -> list[dict[str, Any]]:
        skills = await self.repo.list_skills()
        return [SkillRead.model_validate(s).model_dump(mode="json") for s in skills]
