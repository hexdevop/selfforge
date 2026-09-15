"""The real seed catalog as engine input, shared by engine tests."""

from app.engine.types import CatalogExercise, is_timed
from app.seed import load_catalog

CATALOG = [
    CatalogExercise(
        slug=slug,
        pattern=pattern.value,
        level=ex.difficulty_level,
        title=ex.title_ru,
        timed=is_timed(pattern, ex.progression_criteria and ex.progression_criteria.model_dump()),
        required_equipment=tuple(tuple(g) for g in ex.required_equipment),
        requires_pair=ex.requires_pair,
        is_unilateral=ex.is_unilateral,
        is_quiet=ex.is_quiet,
        needs_floor_space=ex.needs_floor_space,
        needs_ceiling_height=ex.needs_ceiling_height,
        lies_on_floor=ex.lies_on_floor,
        contraindicated_for=frozenset(ex.contraindicated_for),
        prev_slug=ex.prev_slug,
        next_slug=ex.next_slug,
    )
    for slug, (pattern, ex) in load_catalog().exercises.items()
]
BY_SLUG = {e.slug: e for e in CATALOG}


def pattern_exercises(pattern: str) -> list[CatalogExercise]:
    return [e for e in CATALOG if e.pattern == pattern]
