"""Idempotent seed of the reference catalog from `backend/seed/*.yaml`.

    python -m app.seed

Rows are upserted by their stable key (pattern/equipment `code`, exercise/skill `slug`),
so re-running converges to the YAML. Rows removed from YAML are kept: user history
refers to exercises by slug.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.decorator import invalidate_prefix
from app.db.base import Base
from app.db.session import async_session_factory
from app.engine.types import is_timed
from app.models.catalog import EquipmentItem, Exercise, MovementPattern, Skill
from app.schemas.catalog import (
    EquipmentCategory,
    HealthTag,
    Muscle,
    PatternCode,
    ProgressionCriteria,
    SkillPrerequisite,
)
from app.services.catalog import CACHE_PREFIX

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"

_SLUG = r"^[a-z0-9_]+$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PatternSeed(_Strict):
    code: PatternCode
    title_ru: str = Field(min_length=1)
    description_ru: str = Field(min_length=1)
    is_bilateral_default: bool = True


class EquipmentSeed(_Strict):
    code: str = Field(pattern=_SLUG)
    title_ru: str = Field(min_length=1)
    category: EquipmentCategory
    supports_quantity: bool = False
    supports_weight_list: bool = False
    is_outdoor: bool = False


class ExerciseSeed(_Strict):
    slug: str = Field(pattern=_SLUG, max_length=64)
    title_ru: str = Field(min_length=1, max_length=150)
    difficulty_level: int = Field(ge=1)
    # Share of body mass lifted per rep, for tonnage; 0 where the body doesn't travel.
    bodyweight_share: float = Field(default=0, ge=0, le=1)
    is_unilateral: bool = False
    requires_pair: bool = False
    is_quiet: bool = True
    needs_floor_space: bool = False
    needs_ceiling_height: bool = False
    lies_on_floor: bool = False
    required_equipment: list[list[str]] = []
    primary_muscles: list[Muscle] = Field(min_length=1)
    secondary_muscles: list[Muscle] = []
    contraindicated_for: list[HealthTag] = []
    technique_ru: str = Field(min_length=1)
    common_mistakes_ru: list[str] = Field(min_length=2, max_length=3)
    media: dict[str, str] = {}
    prev_slug: str | None = None
    next_slug: str | None = None
    progression_criteria: ProgressionCriteria | None = None


class PatternFile(_Strict):
    pattern: PatternCode
    exercises: list[ExerciseSeed]


class SkillSeed(_Strict):
    slug: str = Field(pattern=_SLUG)
    title_ru: str = Field(min_length=1)
    description_ru: str = Field(min_length=1)
    goal: SkillPrerequisite | None = None
    prerequisites: list[SkillPrerequisite] = []
    lead_up_exercise_slugs: list[str] = Field(min_length=1)


@dataclass(frozen=True)
class Catalog:
    patterns: list[PatternSeed]
    equipment: list[EquipmentSeed]
    exercises: dict[str, tuple[PatternCode, ExerciseSeed]]
    skills: list[SkillSeed]


def _read(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _timed(pattern: PatternCode, ex: ExerciseSeed) -> bool:
    criteria = ex.progression_criteria
    return is_timed(pattern, criteria.model_dump() if criteria else None)


def load_catalog(seed_dir: Path = SEED_DIR) -> Catalog:
    """Parse and cross-validate the YAML; raises ValueError listing every problem."""
    patterns = [PatternSeed.model_validate(p) for p in _read(seed_dir / "patterns.yaml")]
    equipment = [EquipmentSeed.model_validate(e) for e in _read(seed_dir / "equipment.yaml")]
    skills = [SkillSeed.model_validate(s) for s in _read(seed_dir / "skills.yaml")]

    problems: list[str] = []
    exercises: dict[str, tuple[PatternCode, ExerciseSeed]] = {}
    for path in sorted((seed_dir / "exercises").glob("*.yaml")):
        file = PatternFile.model_validate(_read(path))
        if path.stem != file.pattern:
            problems.append(f"{path.name}: pattern is {file.pattern!r}, expected {path.stem!r}")
        for ex in file.exercises:
            if ex.slug in exercises:
                problems.append(f"duplicate exercise slug {ex.slug!r}")
            exercises[ex.slug] = (file.pattern, ex)

    equipment_codes = {e.code for e in equipment}
    pattern_codes = {p.code for p in patterns}
    for code in {pattern for pattern, _ in exercises.values()} - pattern_codes:
        problems.append(f"exercises reference unknown pattern {code!r}")
    for code in pattern_codes - {pattern for pattern, _ in exercises.values()}:
        problems.append(f"pattern {code!r} has no exercises")

    for slug, (pattern, ex) in exercises.items():
        for group in ex.required_equipment:
            if not group:
                problems.append(f"{slug}: empty equipment group")
            for unknown in set(group) - equipment_codes:
                problems.append(f"{slug}: unknown equipment {unknown!r}")
        timed = _timed(pattern, ex)
        if timed and ex.bodyweight_share:
            problems.append(f"{slug}: timed work has no tonnage, bodyweight_share must be 0")
        if ex.requires_pair and not ex.required_equipment:
            problems.append(f"{slug}: requires_pair without equipment")
        for link, must_be_harder in ((ex.prev_slug, False), (ex.next_slug, True)):
            if link is None:
                continue
            target = exercises.get(link)
            if target is None:
                problems.append(f"{slug}: ladder link to unknown {link!r}")
            elif target[0] != pattern:
                problems.append(f"{slug}: ladder link {link!r} crosses patterns")
            elif (target[1].difficulty_level > ex.difficulty_level) != must_be_harder:
                problems.append(f"{slug}: ladder link {link!r} goes the wrong way")

    for skill in skills:
        goal = [skill.goal] if skill.goal else []
        referenced = skill.lead_up_exercise_slugs + [
            p.exercise_slug for p in [*skill.prerequisites, *goal]
        ]
        for slug in set(referenced) - exercises.keys():
            problems.append(f"skill {skill.slug}: unknown exercise {slug!r}")
        for result in [*skill.prerequisites, *goal]:
            if result.exercise_slug not in exercises:
                continue
            pattern, ex = exercises[result.exercise_slug]
            timed = _timed(pattern, ex)
            if timed != (result.hold_seconds is not None):
                problems.append(
                    f"skill {skill.slug}: {result.exercise_slug!r} is measured in "
                    f"{'seconds' if timed else 'reps'}"
                )

    if problems:
        raise ValueError("Invalid seed data:\n  " + "\n  ".join(sorted(problems)))
    return Catalog(patterns, equipment, exercises, skills)


async def _upsert(
    session: AsyncSession, model: type[Base], key: str, rows: list[dict[str, Any]]
) -> None:
    stmt = insert(model).values(rows)
    update = {column: stmt.excluded[column] for column in rows[0] if column != key}
    await session.execute(
        stmt.on_conflict_do_update(index_elements=[key], set_={**update, "updated_at": func.now()})
    )


async def seed(session: AsyncSession, catalog: Catalog) -> None:
    await _upsert(
        session, MovementPattern, "code", [p.model_dump(mode="json") for p in catalog.patterns]
    )
    await _upsert(
        session, EquipmentItem, "code", [e.model_dump(mode="json") for e in catalog.equipment]
    )

    exercise_rows = []
    for pattern, ex in catalog.exercises.values():
        row = ex.model_dump(mode="json", exclude={"progression_criteria"})
        criteria = ex.progression_criteria
        row["progression_criteria"] = criteria.model_dump(exclude_none=True) if criteria else None
        exercise_rows.append({**row, "pattern_code": pattern.value})
    await _upsert(session, Exercise, "slug", exercise_rows)

    await _upsert(session, Skill, "slug", [s.model_dump(mode="json") for s in catalog.skills])
    await session.commit()


async def main() -> None:
    catalog = load_catalog()
    async with async_session_factory() as session:
        await seed(session, catalog)
    await invalidate_prefix(CACHE_PREFIX)
    print(
        f"Seeded {len(catalog.patterns)} patterns, {len(catalog.equipment)} equipment items, "
        f"{len(catalog.exercises)} exercises, {len(catalog.skills)} skills"
    )


if __name__ == "__main__":
    asyncio.run(main())
