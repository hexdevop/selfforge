from decimal import Decimal

import pytest

from app.engine.goals import Goal, Lever
from app.engine.progression import Performance, Prescription, next_progression
from app.engine.types import Constraints, Equipment, Location, Surface
from tests.engine.catalog import CATALOG

D = Decimal

HOUSEHOLD = {code: Equipment(code) for code in ("chair", "sofa", "wall", "towel")}


def home(*items: Equipment) -> Location:
    return Location("home", {**HOUSEHOLD, **{e.code: e for e in items}})


PARK = Location(
    "park",
    {c: Equipment(c) for c in ("pullup_bar", "parallel_bars", "low_bar")},
    Constraints(surface=Surface.SAND),
    kind="outdoor_gym",
)
KB16 = Equipment("kettlebell", weights_kg=(D(16),))
DB_PAIR_16 = Equipment("dumbbell", quantity=2, weights_kg=(D(16),))
DB_PAIRS = Equipment("dumbbell", quantity=2, weights_kg=(D(10), D(12), D(14), D(16)))
BENCH = Equipment("bench")


def rx(
    exercise: str,
    weight: str | None = None,
    sets: int = 3,
    target: tuple[int, int] = (8, 12),
    rest_seconds: int = 90,
    tempo: str | None = None,
) -> Prescription:
    return Prescription(exercise, sets, target, rest_seconds, D(weight) if weight else None, tempo)


def done(p: Prescription, *reps: int) -> Performance:
    return Performance(p, reps)


def decide(
    history: list[Performance],
    location: Location,
    goal: Goal = Goal.HYPERTROPHY,
    health: tuple[str, ...] = (),
) -> tuple[Lever, Prescription, str]:
    d = next_progression(history, goal, location, CATALOG, health)
    return d.lever, d.prescription, d.explanation_ru


def test_below_the_top_keeps_adding_reps() -> None:
    p = rx("db_floor_press", "12")
    lever, nxt, text = decide([done(p, 12, 11, 10)], home(DB_PAIRS))
    assert (lever, nxt) == (Lever.REPS, p)
    assert "12 повторов" in text


def test_top_of_the_range_adds_the_smallest_weight_step() -> None:
    lever, nxt, text = decide([done(rx("db_floor_press", "12"), 12, 12, 12)], home(DB_PAIRS))
    assert lever is Lever.WEIGHT
    assert nxt.weight_kg == D(14)
    assert "14 кг" in text and "с 8 повторов" in text


def test_fixed_pair_at_its_ceiling_moves_up_the_ladder() -> None:
    p = rx("db_bench_press", "16")
    lever, nxt, text = decide([done(p, 12, 12, 12)], home(DB_PAIR_16, BENCH))
    assert lever is Lever.DIFFICULTY
    assert nxt.exercise == "archer_pushup"
    assert nxt.weight_kg is None
    assert "тяжелее снаряда здесь нет" in text


def test_ladder_step_skips_what_health_rules_out() -> None:
    p = rx("db_bench_press", "16")
    lever, nxt, _ = decide([done(p, 12, 12, 12)], home(DB_PAIR_16, BENCH), health=("shoulders",))
    assert lever is Lever.DIFFICULTY
    assert nxt.exercise == "one_arm_incline_pushup"


def test_single_kettlebell_strength_goes_to_harder_variation() -> None:
    p = rx("goblet_squat", "16", sets=4, target=(3, 6), rest_seconds=180)
    lever, nxt, _ = decide([done(p, 6, 6, 6, 6)], home(KB16), Goal.STRENGTH)
    assert lever is Lever.DIFFICULTY
    assert nxt.exercise == "split_squat"


def test_one_sided_variant_when_there_is_no_harder_step() -> None:
    # A hotel room with a pair of 16s: no bench, no chair, and archer push-ups are out
    # with bad shoulders — but pressing one dumbbell at a time is still there.
    hotel = Location("hotel", {"dumbbell": DB_PAIR_16})
    p = rx("db_floor_press", "16")
    lever, nxt, text = decide([done(p, 12, 12, 12)], hotel, health=("shoulders",))
    assert lever is Lever.UNILATERAL
    assert nxt.exercise == "single_arm_floor_press"
    assert nxt.weight_kg == D(16)
    assert "поровну" in text


def test_tempo_then_volume_when_nothing_else_is_left() -> None:
    # Top of the pull-up ladder here: nothing harder, nothing one-sided at this level.
    p = rx("muscle_up", target=(3, 6))
    lever, nxt, _ = decide([done(p, 6, 6, 6)], PARK)
    assert (lever, nxt.tempo) == (Lever.TEMPO, "3-0-1")
    lever, nxt, _ = decide([done(nxt, 6, 6, 6)], PARK)
    assert (lever, nxt.tempo) == (Lever.TEMPO, "3-2-1")
    lever, nxt, _ = decide([done(nxt, 6, 6, 6)], PARK)
    assert (lever, nxt.sets) == (Lever.VOLUME, 4)


def test_ceiling_when_every_lever_is_spent() -> None:
    p = rx("muscle_up", target=(3, 6), sets=5, tempo="3-2-1")
    lever, nxt, text = decide([done(p, 6, 6, 6, 6, 6)], PARK)
    assert (lever, nxt) == (Lever.CEILING, p)
    assert "потолок" in text


def test_conditioning_goals_cut_rest_before_changing_the_exercise() -> None:
    p = rx("db_floor_press", "16", target=(15, 25), rest_seconds=45)
    lever, nxt, _ = decide([done(p, 25, 25, 25)], home(DB_PAIRS), Goal.ENDURANCE)
    assert (lever, nxt.rest_seconds) == (Lever.DENSITY, 30)


def test_skill_never_adds_weight() -> None:
    p = rx("db_floor_press", "12", target=(3, 6))
    lever, nxt, _ = decide([done(p, 6, 6, 6)], home(DB_PAIRS), Goal.SKILL)
    assert lever is Lever.DIFFICULTY
    assert nxt.exercise == "decline_pushup"


def test_timed_exercise_counts_seconds() -> None:
    p = rx("plank", target=(20, 40))
    lever, _, text = decide([done(p, 40, 35, 30)], home())
    assert lever is Lever.REPS
    assert "40 секунд" in text


def test_three_failed_sessions_take_about_ten_percent_off() -> None:
    p = rx("db_floor_press", "16")
    lever, nxt, text = decide([done(p, 7, 6, 6)] * 3, home(DB_PAIRS))
    assert lever is Lever.ROLLBACK
    assert nxt.weight_kg == D(14)  # 16 × 0.9 = 14.4 → the closest real weight
    assert "Три тренировки подряд" in text


def test_rollback_steps_down_the_ladder_without_a_lighter_weight() -> None:
    p = rx("pullup", target=(3, 6))
    lever, nxt, _ = decide([done(p, 2, 2, 1)] * 3, PARK)
    assert (lever, nxt.exercise) == (Lever.ROLLBACK, "negative_pullup")


@pytest.mark.parametrize(
    "reps",
    [
        pytest.param([(7, 6, 6), (7, 6, 6)], id="only two bad sessions"),
        pytest.param([(7, 6, 6), (8, 8, 8), (7, 6, 6)], id="streak broken"),
        pytest.param([(10, 8, 6)] * 3, id="one weak set is not a failed session"),
    ],
)
def test_no_rollback(reps: list[tuple[int, ...]]) -> None:
    p = rx("db_floor_press", "16")
    lever, _, _ = decide([done(p, *r) for r in reps], home(DB_PAIRS))
    assert lever is Lever.REPS


def test_failed_sessions_on_another_exercise_do_not_count() -> None:
    old, new = rx("knee_pushup"), rx("pushup")
    history = [done(old, 3, 3, 3), done(old, 3, 3, 3), done(new, 3, 3, 3)]
    lever, _, _ = decide(history, home())
    assert lever is Lever.REPS
