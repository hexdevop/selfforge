from decimal import Decimal

import pytest

from app.engine.inventory import (
    is_available,
    min_step,
    plate_breakdown,
    resolve_available_exercises,
    weight_grid,
)
from app.engine.types import CatalogExercise, Constraints, Equipment, Location, Plate, Surface
from app.seed import load_catalog

D = Decimal  # short alias keeps the weight tables readable

CATALOG = [
    CatalogExercise(
        slug=slug,
        pattern=pattern.value,
        level=ex.difficulty_level,
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

HOUSEHOLD = {code: Equipment(code) for code in ("chair", "sofa", "wall", "towel")}


def home(*items: Equipment, **constraints: bool) -> Location:
    return Location("home", {**HOUSEHOLD, **{e.code: e for e in items}}, Constraints(**constraints))


def available(location: Location, health: tuple[str, ...] = ()) -> set[str]:
    return {e.slug for e in resolve_available_exercises([location], health, CATALOG)[location.id]}


ONE_KETTLEBELL = Equipment("kettlebell", weights_kg=(D(16),))
ONE_DUMBBELL = Equipment("dumbbell", quantity=1, weights_kg=(D(10),))


@pytest.mark.parametrize(
    ("location", "health", "must_have", "must_not_have"),
    [
        pytest.param(
            home(ONE_KETTLEBELL),
            (),
            {"goblet_squat", "kb_swing", "single_arm_floor_press", "kb_row", "turkish_getup"},
            {"double_kb_front_squat", "farmer_carry", "db_bench_press", "pullup"},
            id="one kettlebell: single-bell school, nothing needing a pair",
        ),
        pytest.param(
            home(Equipment("kettlebell", weights_kg=(D(16), D(16), D(24)))),
            (),
            {"double_kb_front_squat", "farmer_carry", "mixed_carry"},
            set(),
            id="two equal kettlebells make a pair",
        ),
        pytest.param(
            home(ONE_DUMBBELL),
            (),
            {"one_arm_db_row", "goblet_squat", "single_arm_overhead_press"},
            {"db_bench_press", "db_floor_press", "bent_over_db_row", "db_overhead_press"},
            id="one dumbbell: only one-arm work",
        ),
        pytest.param(
            home(Equipment("dumbbell", quantity=2, weights_kg=(D(16),)), Equipment("bench")),
            (),
            {"db_bench_press", "db_floor_press", "db_overhead_press", "seated_db_press"},
            set(),
            id="pair of dumbbells and a bench",
        ),
        pytest.param(
            home(Equipment("jump_rope"), quiet_mode=True),
            (),
            {"air_squat", "squat_thrust", "pushup"},
            {"jump_rope", "jump_squat", "jumping_lunge", "burpee", "barbell_deadlift"},
            id="quiet mode: no jumps, no rope, no dropped iron",
        ),
        pytest.param(
            home(ONE_KETTLEBELL, Equipment("resistance_band"), low_ceiling=True),
            (),
            {"half_kneeling_press", "single_arm_floor_press"},
            {"single_arm_overhead_press", "band_overhead_press", "push_press", "kb_snatch"},
            id="low ceiling: no standing overhead work",
        ),
        pytest.param(
            home(limited_space=True),
            (),
            {"reverse_lunge", "forward_lunge"},
            {"walking_lunge"},
            id="limited space: no travelling exercises",
        ),
        pytest.param(
            Location(
                "park",
                {c: Equipment(c) for c in ("pullup_bar", "parallel_bars", "low_bar")},
                Constraints(surface=Surface.SAND),
            ),
            (),
            {"pullup", "parallel_bar_dips", "australian_pullup_low", "hanging_knee_raise"},
            {"glute_bridge", "dead_bug", "burpee", "hollow_hold"},
            id="sand: bars yes, lying on the ground no",
        ),
        pytest.param(
            home(ONE_KETTLEBELL),
            ("knees",),
            {"box_squat", "air_squat", "goblet_squat", "split_squat"},
            {"pistol_squat", "jump_squat", "bulgarian_split_squat", "box_pistol", "nordic_curl"},
            id="knee restriction: squat only from safe variants",
        ),
    ],
)
def test_available_exercises(
    location: Location, health: tuple[str, ...], must_have: set[str], must_not_have: set[str]
) -> None:
    result = available(location, health)
    assert must_have <= result, must_have - result
    assert not must_not_have & result, must_not_have & result


def test_nothing_needed_means_available_anywhere() -> None:
    hotel = Location("travel", {})
    assert is_available(BY_SLUG["pushup"], hotel)
    assert not is_available(BY_SLUG["wall_sit"], hotel)


def test_pair_must_come_from_one_kind_of_implement() -> None:
    mixed = home(ONE_KETTLEBELL, ONE_DUMBBELL)
    assert not is_available(BY_SLUG["farmer_carry"], mixed)


ADJUSTABLE_PAIR = Equipment(
    "dumbbell",
    quantity=2,
    bar_kg=D("2.0"),
    plates=(Plate(D("1.25"), 4), Plate(D("2.5"), 4), Plate(D(5), 2)),
)


@pytest.mark.parametrize(
    ("equipment", "grid"),
    [
        pytest.param(
            Equipment("kettlebell", weights_kg=(D(24), D(16), D(16))),
            [D(16), D(24)],
            id="kettlebells: distinct weights",
        ),
        pytest.param(
            ADJUSTABLE_PAIR,
            [D("2.0"), D("4.5"), D("7.0"), D("9.5")],
            id="adjustable pair: 5 kg plates can't load both handles evenly",
        ),
        pytest.param(
            Equipment(
                "dumbbell",
                quantity=1,
                bar_kg=D("2.0"),
                plates=(Plate(D("1.25"), 4), Plate(D("2.5"), 4), Plate(D(5), 2)),
            ),
            [
                D("2.0"),
                D("4.5"),
                D("7.0"),
                D("9.5"),
                D("12.0"),
                D("14.5"),
                D("17.0"),
                D("19.5"),
                D("22.0"),
                D("24.5"),
                D("27.0"),
            ],
            id="single adjustable dumbbell gets every plate",
        ),
        pytest.param(
            Equipment("barbell", bar_kg=D(10), plates=(Plate(D(5), 2), Plate(D("0.5"), 2))),
            [D(10), D(11), D(20), D(21)],
            id="odd micro plates",
        ),
    ],
)
def test_weight_grid(equipment: Equipment, grid: list[D]) -> None:
    assert weight_grid(equipment) == grid


def test_min_step() -> None:
    assert min_step(weight_grid(ADJUSTABLE_PAIR)) == D("2.5")
    assert min_step([D(16)]) is None


def bar(*plates: tuple[str, int]) -> Equipment:
    return Equipment("barbell", bar_kg=D("2.5"), plates=tuple(Plate(D(kg), n) for kg, n in plates))


@pytest.mark.parametrize(
    ("equipment", "target", "expected"),
    [
        pytest.param(
            bar(("5", 2), ("2.5", 4)),
            D("17.5"),
            [Plate(D(5), 1), Plate(D("2.5"), 1)],
            id="docs example: 2.5 + 5 per side",
        ),
        pytest.param(bar(("5", 2)), D("2.5"), [], id="empty bar"),
        pytest.param(
            bar(("3", 2), ("2", 4)),
            D("10.5"),
            [Plate(D(2), 2)],
            id="heaviest-first dead end backtracks",
        ),
        pytest.param(bar(("5", 2), ("2.5", 4)), D("18"), None, id="off the grid"),
        pytest.param(bar(("5", 2)), D("1"), None, id="lighter than the bar"),
    ],
)
def test_plate_breakdown(equipment: Equipment, target: D, expected: list[Plate] | None) -> None:
    assert plate_breakdown(target, equipment) == expected


def test_plate_breakdown_needs_adjustable_equipment() -> None:
    assert plate_breakdown(D(16), ONE_KETTLEBELL) is None
