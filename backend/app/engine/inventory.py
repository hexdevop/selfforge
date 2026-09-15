"""What can be done with a given inventory (docs/03-engine.md §1)."""

from collections.abc import Collection, Iterable
from decimal import Decimal

from app.engine.types import CatalogExercise, Equipment, Location, Plate, Surface

_NO_LYING = {Surface.SAND, Surface.ASPHALT}


def is_available(
    exercise: CatalogExercise, location: Location, health_flags: Collection[str] = ()
) -> bool:
    c = location.constraints
    if (
        (c.quiet_mode and not exercise.is_quiet)
        or (c.low_ceiling and exercise.needs_ceiling_height)
        or (c.limited_space and exercise.needs_floor_space)
        or (c.surface in _NO_LYING and exercise.lies_on_floor)
        or exercise.contraindicated_for.intersection(health_flags)
    ):
        return False

    owned = location.equipment
    if not all(any(code in owned for code in group) for group in exercise.required_equipment):
        return False
    # A pair must come from one kind of implement: two dumbbells, not a dumbbell and a kettlebell.
    return not exercise.requires_pair or any(
        owned[code].has_pair
        for group in exercise.required_equipment
        for code in group
        if code in owned
    )


def resolve_available_exercises(
    locations: Iterable[Location],
    health_flags: Collection[str],
    catalog: Iterable[CatalogExercise],
) -> dict[str, list[CatalogExercise]]:
    catalog = list(catalog)
    return {loc.id: [e for e in catalog if is_available(e, loc, health_flags)] for loc in locations}


def _per_side_limits(equipment: Equipment) -> list[tuple[Decimal, int]]:
    """Plates usable on one side of one implement: both sides and all pieces load alike."""
    per_side: dict[Decimal, int] = {}
    for plate in equipment.plates:
        per_side[plate.kg] = per_side.get(plate.kg, 0) + plate.count // (2 * equipment.quantity)
    return sorted(((kg, n) for kg, n in per_side.items() if n > 0), reverse=True)


def weight_grid(equipment: Equipment, pair: bool = False) -> list[Decimal]:
    """Every weight one implement can be set to, ascending. Nothing outside it is ever offered.

    `pair`: only weights there are two pieces of — two 16 kg kettlebells, not a 16 and a 24.
    """
    if equipment.bar_kg is None:
        weights = equipment.weights_kg
        if pair and equipment.quantity < 2:
            weights = tuple(w for w in weights if weights.count(w) > 1)
        return sorted(set(weights))

    # ponytail: enumerates reachable sums; fine for home plate sets (a few dozen plates).
    sides = {Decimal(0)}
    for kg, limit in _per_side_limits(equipment):
        sides = {s + kg * n for s in sides for n in range(limit + 1)}
    return sorted(equipment.bar_kg + 2 * s for s in sides)


def min_step(grid: list[Decimal]) -> Decimal | None:
    steps = [b - a for a, b in zip(grid, grid[1:], strict=False)]
    return min(steps) if steps else None


def plate_breakdown(target_kg: Decimal, equipment: Equipment) -> list[Plate] | None:
    """Plates to hang on EACH side to reach `target_kg`, heaviest first; None if unreachable."""
    if equipment.bar_kg is None:
        return None
    side = (target_kg - equipment.bar_kg) / 2
    if side < 0:
        return None
    limits = _per_side_limits(equipment)

    def search(i: int, rest: Decimal) -> list[Plate] | None:
        if rest == 0:
            return []
        if i == len(limits):
            return None
        kg, limit = limits[i]
        for n in range(min(limit, int(rest // kg)), -1, -1):
            tail = search(i + 1, rest - kg * n)
            if tail is not None:
                return ([Plate(kg, n)] if n else []) + tail
        return None

    return search(0, side)
