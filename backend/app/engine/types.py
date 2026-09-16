from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class Surface(StrEnum):
    RUBBER = "rubber"
    SAND = "sand"
    ASPHALT = "asphalt"


@dataclass(frozen=True)
class Plate:
    kg: Decimal
    count: int


@dataclass(frozen=True)
class Equipment:
    """One kind of equipment at a location.

    Adjustable implements (barbell, adjustable dumbbells) have `bar_kg` + `plates`;
    fixed ones (fixed dumbbells, kettlebells) list their `weights_kg`, one entry per
    piece — two 16 kg kettlebells are `(16, 16)`.
    """

    code: str
    quantity: int = 1
    bar_kg: Decimal | None = None
    plates: tuple[Plate, ...] = ()
    weights_kg: tuple[Decimal, ...] = ()

    @property
    def has_pair(self) -> bool:
        return self.quantity >= 2 or len(self.weights_kg) > len(set(self.weights_kg))


@dataclass(frozen=True)
class Constraints:
    quiet_mode: bool = False
    low_ceiling: bool = False
    limited_space: bool = False
    surface: Surface | None = None


@dataclass(frozen=True)
class Location:
    id: str
    equipment: Mapping[str, Equipment]
    constraints: Constraints = field(default_factory=Constraints)
    kind: str = "home"
    title: str = ""


@dataclass(frozen=True)
class CatalogExercise:
    slug: str
    pattern: str
    level: int
    title: str = ""
    # Measured in seconds of work (planks, carries, cardio), not in reps.
    timed: bool = False
    # Share of body mass lifted per rep, for tonnage; 0 where the body doesn't travel.
    bodyweight_share: Decimal = Decimal(0)
    # AND of OR-groups of equipment codes; empty means bodyweight only.
    required_equipment: tuple[tuple[str, ...], ...] = ()
    requires_pair: bool = False
    is_unilateral: bool = False
    is_quiet: bool = True
    needs_floor_space: bool = False
    needs_ceiling_height: bool = False
    lies_on_floor: bool = False
    contraindicated_for: frozenset[str] = frozenset()
    prev_slug: str | None = None
    next_slug: str | None = None


def is_timed(pattern: str, criteria: Mapping[str, object] | None) -> bool:
    """Carries and cardio are timed by nature; the rest when their criteria are in seconds."""
    if criteria:
        return bool(criteria.get("hold_seconds"))
    return pattern in ("carry", "cardio")
