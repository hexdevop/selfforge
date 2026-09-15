"""Difficulty ladders (docs/01-domain.md): one scale per pattern, a main line through it."""

from collections.abc import Iterable

from app.engine.types import CatalogExercise


def main_line(exercises: Iterable[CatalogExercise]) -> list[CatalogExercise]:
    """The ladder's backbone: start at the easiest step and follow `next_slug`.

    Variants on other equipment point into the line but are not on it.
    """
    by_slug = {e.slug: e for e in exercises}
    if not by_slug:
        return []
    step: CatalogExercise | None = min(
        by_slug.values(), key=lambda e: (e.level, e.prev_slug is not None, e.slug)
    )
    line: list[CatalogExercise] = []
    while step is not None and step not in line:
        line.append(step)
        step = by_slug.get(step.next_slug) if step.next_slug else None
    return line


def step_at(line: list[CatalogExercise], level: int) -> CatalogExercise:
    """Hardest main-line step not above `level` (the easiest one if all are above)."""
    fitting = [e for e in line if e.level <= level]
    return fitting[-1] if fitting else line[0]
