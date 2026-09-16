from decimal import Decimal

import pytest

from app.engine.goals import Goal
from app.engine.mesocycle import BlockKind, PlannedDay, ProgramInput, build_mesocycle
from app.engine.progression import Performance, Prescription
from app.engine.session import (
    Feeling,
    Readiness,
    Session,
    SessionExercise,
    SubstitutionReason,
    matched_reps,
    prepare_session,
    substitute_exercise,
    trim_session,
)
from app.engine.types import Constraints, Equipment, Location, Surface
from tests.engine.catalog import BY_SLUG, CATALOG

D = Decimal

HOUSEHOLD = {code: Equipment(code) for code in ("chair", "sofa", "wall", "towel")}
KB16 = Equipment("kettlebell", weights_kg=(D(16),))
DUMBBELLS = Equipment("dumbbell", quantity=2, weights_kg=(D(8), D(8), D(12), D(12), D(16), D(16)))

LEVELS = {
    "squat": 3,
    "hinge": 2,
    "push_h": 4,
    "push_v": 3,
    "pull_h": 2,
    "pull_v": 2,
    "lunge": 3,
    "core": 2,
    "carry": 1,
    "cardio": 1,
}


def home(*items: Equipment, **constraints: bool) -> Location:
    return Location(
        "home",
        {**HOUSEHOLD, **{e.code: e for e in items}},
        Constraints(**constraints),
        kind="home",
        title="Дом",
    )


PARK = Location(
    "park",
    {c: Equipment(c) for c in ("pullup_bar", "parallel_bars", "low_bar")},
    Constraints(surface=Surface.SAND),
    kind="outdoor_gym",
    title="Площадка",
)


def plan(
    location: Location, goal: Goal = Goal.HYPERTROPHY, minutes: int = 45, week: int = 0
) -> PlannedDay:
    program = build_mesocycle(
        ProgramInput(
            goal=goal,
            secondary_goal=None,
            session_minutes=minutes,
            levels=LEVELS,
            day_locations=(location.id,) * 3,
        ),
        {location.id: location},
        CATALOG,
    )
    return program.weeks[week].days[0]


def prepare(
    location: Location,
    history: dict[str, list[Performance]] | None = None,
    readiness: Readiness = Readiness(),
    goal: Goal = Goal.HYPERTROPHY,
    minutes: int = 45,
) -> Session:
    return prepare_session(
        plan(location, goal, minutes), history or {}, readiness, location, CATALOG, goal
    )


def block(session: Session, kind: BlockKind) -> list[SessionExercise]:
    return [e for b in session.blocks if b.kind is kind for e in b.exercises]


def all_exercises(session: Session) -> list[SessionExercise]:
    return [e for b in session.blocks for e in b.exercises]


# --- readiness ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("taps", "multiplier"),
    [
        ((Feeling.BAD, Feeling.BAD, Feeling.BAD), D("0.7")),
        ((Feeling.BAD, Feeling.BAD, Feeling.OK), D("0.8")),
        ((Feeling.BAD, Feeling.OK, Feeling.OK), D("0.9")),
        ((Feeling.OK, Feeling.OK, Feeling.OK), D("1.0")),
        ((Feeling.GOOD, Feeling.OK, Feeling.OK), D("1.05")),
        ((Feeling.GOOD, Feeling.GOOD, Feeling.GOOD), D("1.1")),
    ],
)
def test_readiness_scales_volume_inside_the_documented_band(
    taps: tuple[Feeling, Feeling, Feeling], multiplier: Decimal
) -> None:
    assert Readiness(*taps).volume_multiplier == multiplier


def test_low_readiness_cuts_the_extras_and_leaves_the_main_movements_alone() -> None:
    location = home(KB16)
    normal = prepare(location, goal=Goal.FAT_LOSS)
    tired = prepare(
        location,
        readiness=Readiness(Feeling.BAD, Feeling.BAD, Feeling.BAD),
        goal=Goal.FAT_LOSS,
    )

    assert [e.sets for e in block(tired, BlockKind.MAIN)] == [
        e.sets for e in block(normal, BlockKind.MAIN)
    ]
    assert block(normal, BlockKind.FINISHER) and not block(tired, BlockKind.FINISHER)
    assert sum(e.sets for e in block(tired, BlockKind.ACCESSORY)) < sum(
        e.sets for e in block(normal, BlockKind.ACCESSORY)
    )
    assert tired.notes_ru and "ниже обычной" in tired.notes_ru[0]


def test_high_readiness_adds_volume_and_keeps_the_finisher() -> None:
    location = home(KB16)
    normal = prepare(location, goal=Goal.FAT_LOSS)
    fresh = prepare(
        location,
        readiness=Readiness(Feeling.GOOD, Feeling.GOOD, Feeling.GOOD),
        goal=Goal.FAT_LOSS,
    )
    assert sum(e.sets for e in all_exercises(fresh)) > sum(e.sets for e in all_exercises(normal))
    assert block(fresh, BlockKind.FINISHER)


def test_a_normal_day_says_nothing_about_readiness() -> None:
    assert prepare(home(KB16)).notes_ru == ()


# --- warm-up and cool-down ------------------------------------------------------------


def test_warmup_covers_the_patterns_of_this_day_and_cooldown_is_there() -> None:
    session = prepare(home(KB16, DUMBBELLS))
    warmup = next(b for b in session.blocks if b.kind is BlockKind.WARMUP)
    cooldown = next(b for b in session.blocks if b.kind is BlockKind.COOLDOWN)

    assert len(warmup.drills) > 2 and not warmup.exercises
    assert cooldown.drills and not cooldown.exercises
    text = " ".join(d.title_ru for d in warmup.drills)
    assert "Суставная разминка" in text
    assert sum(d.seconds for d in warmup.drills) <= warmup.minutes * 60


@pytest.mark.parametrize("minutes", [20, 30, 45, 60])
def test_a_short_warmup_still_gets_at_least_the_general_part(minutes: int) -> None:
    session = prepare(home(KB16), minutes=minutes)
    warmup = next(b for b in session.blocks if b.kind is BlockKind.WARMUP)
    assert warmup.drills


# --- weights from history -------------------------------------------------------------


def test_the_first_time_starts_at_the_lightest_weight_that_exists_here() -> None:
    session = prepare(home(DUMBBELLS))
    loaded = [e for e in all_exercises(session) if e.weight_kg is not None]
    assert loaded, "dumbbells at home should give at least one loaded exercise"
    for e in loaded:
        assert e.weight_kg == D(8)
        assert "Первый раз" in e.hint_ru


def test_timed_exercises_never_get_a_weight() -> None:
    for e in all_exercises(prepare(home(KB16, DUMBBELLS))):
        if e.timed:
            assert e.weight_kg is None


def test_topping_the_range_last_time_moves_the_weight_up() -> None:
    location = home(DUMBBELLS)
    day = plan(location)
    first = [e for b in day.blocks if b.kind is BlockKind.MAIN for e in b.exercises][0]
    done = Performance(
        Prescription(first.exercise, first.sets, first.target, first.rest_seconds, D(8)),
        (first.target[1],) * first.sets,
    )
    session = prepare_session(
        day, {first.exercise: [done]}, Readiness(), location, CATALOG, Goal.HYPERTROPHY
    )
    prepared = block(session, BlockKind.MAIN)[0]
    assert prepared.weight_kg == D(12)
    assert prepared.hint_ru


def test_three_failed_sessions_in_a_row_roll_the_weight_back() -> None:
    location = home(DUMBBELLS)
    day = plan(location)
    first = [e for b in day.blocks if b.kind is BlockKind.MAIN for e in b.exercises][0]
    prescription = Prescription(first.exercise, first.sets, first.target, first.rest_seconds, D(16))
    failed = Performance(prescription, (1,) * first.sets)
    session = prepare_session(
        day, {first.exercise: [failed] * 3}, Readiness(), location, CATALOG, Goal.HYPERTROPHY
    )
    prepared = block(session, BlockKind.MAIN)[0]
    assert prepared.weight_kg is not None and prepared.weight_kg < D(16)
    assert "Три тренировки подряд" in prepared.hint_ru


def test_a_slot_that_moved_up_the_ladder_keeps_progressing_from_what_was_done() -> None:
    """History is keyed by the planned slug but names what was actually performed."""
    location = home(DUMBBELLS)
    day = plan(location)
    planned = [e for b in day.blocks if b.kind is BlockKind.MAIN for e in b.exercises][0]
    moved_to = BY_SLUG[planned.exercise].next_slug
    if moved_to is None:
        pytest.skip("the picked main exercise is the top of its ladder")
    done = Performance(
        Prescription(moved_to, planned.sets, planned.target, planned.rest_seconds, D(8)),
        (planned.target[0],) * planned.sets,
    )
    session = prepare_session(
        day, {planned.exercise: [done]}, Readiness(), location, CATALOG, Goal.HYPERTROPHY
    )
    assert block(session, BlockKind.MAIN)[0].exercise == moved_to


# --- substitution ---------------------------------------------------------------------


def loaded_main(location: Location) -> SessionExercise:
    session = prepare(location)
    return block(session, BlockKind.MAIN)[0]


@pytest.mark.parametrize(
    ("reason", "harder"),
    [(SubstitutionReason.TOO_HARD, False), (SubstitutionReason.TOO_EASY, True)],
)
def test_too_hard_and_too_easy_move_along_the_ladder(
    reason: SubstitutionReason, harder: bool
) -> None:
    location = home(KB16, DUMBBELLS)
    current = loaded_main(location)
    swap = substitute_exercise(current, reason, location, CATALOG, Goal.HYPERTROPHY)
    assert swap is not None
    assert swap.pattern == current.pattern
    before, after = BY_SLUG[current.exercise].level, BY_SLUG[swap.exercise].level
    assert (after > before) if harder else (after < before)
    assert swap.hint_ru


def test_a_busy_implement_is_swapped_for_something_that_does_not_need_it() -> None:
    location = home(KB16, DUMBBELLS)
    current = next(e for e in all_exercises(prepare(location)) if e.weight_kg is not None)
    swap = substitute_exercise(
        current, SubstitutionReason.EQUIPMENT_BUSY, location, CATALOG, Goal.HYPERTROPHY
    )
    assert swap is not None
    needed = {c for g in BY_SLUG[current.exercise].required_equipment for c in g}
    offered = {c for g in BY_SLUG[swap.exercise].required_equipment for c in g}
    assert not (needed & offered)
    assert "занят" in swap.hint_ru.lower()


def test_a_substitution_is_never_something_already_in_the_session() -> None:
    location = home(KB16, DUMBBELLS)
    session = prepare(location)
    current = block(session, BlockKind.MAIN)[0]
    used = {e.exercise for e in all_exercises(session)}
    swap = substitute_exercise(
        current, SubstitutionReason.DISLIKED, location, CATALOG, Goal.HYPERTROPHY, used=used
    )
    assert swap is not None and swap.exercise not in used


def test_a_substitution_stays_inside_what_is_doable_here() -> None:
    location = PARK
    current = block(prepare(location), BlockKind.MAIN)[0]
    swap = substitute_exercise(
        current, SubstitutionReason.DISLIKED, location, CATALOG, Goal.HYPERTROPHY
    )
    assert swap is not None
    assert not (
        {c for g in BY_SLUG[swap.exercise].required_equipment for c in g} - set(location.equipment)
    )


def test_no_alternative_here_means_no_substitution() -> None:
    location = home(KB16)
    current = block(prepare(location), BlockKind.MAIN)[0]
    used = {e.slug for e in CATALOG if e.pattern == current.pattern}
    swap = substitute_exercise(
        current, SubstitutionReason.PAIN, location, CATALOG, Goal.HYPERTROPHY, used=used
    )
    assert swap is None


def test_pain_does_not_hand_out_medical_advice() -> None:
    location = home(KB16, DUMBBELLS)
    swap = substitute_exercise(
        loaded_main(location), SubstitutionReason.PAIN, location, CATALOG, Goal.HYPERTROPHY
    )
    assert swap is not None
    assert "врач" not in swap.hint_ru and "лечен" not in swap.hint_ru


# --- trimming -------------------------------------------------------------------------


def test_trimming_drops_the_extras_before_touching_the_main_work() -> None:
    session = prepare(home(KB16, DUMBBELLS), goal=Goal.FAT_LOSS, minutes=60)
    main_before = block(session, BlockKind.MAIN)
    trimmed = trim_session(session, 25)

    assert [e.exercise for e in block(trimmed, BlockKind.MAIN)] == [e.exercise for e in main_before]
    assert len(all_exercises(trimmed)) < len(all_exercises(session))
    assert trimmed.minutes <= 25


def test_trimming_never_cuts_the_warmup() -> None:
    session = prepare(home(KB16, DUMBBELLS), minutes=60)
    warmup = next(b for b in session.blocks if b.kind is BlockKind.WARMUP)
    trimmed = trim_session(session, 10)
    assert next(b for b in trimmed.blocks if b.kind is BlockKind.WARMUP) == warmup


def test_a_very_short_window_keeps_every_main_movement_on_fewer_sets() -> None:
    session = prepare(home(KB16, DUMBBELLS), minutes=60)
    main_before = block(session, BlockKind.MAIN)
    trimmed = trim_session(session, 12)
    main_after = block(trimmed, BlockKind.MAIN)

    assert [e.exercise for e in main_after] == [e.exercise for e in main_before]
    assert all(e.sets >= 1 for e in main_after)
    assert sum(e.sets for e in main_after) < sum(e.sets for e in main_before)
    assert not block(trimmed, BlockKind.ACCESSORY)
    assert "Главные движения дня остались" in trimmed.notes_ru[-1]


def test_trimming_to_the_time_already_needed_changes_nothing() -> None:
    session = prepare(home(KB16, DUMBBELLS), minutes=45)
    trimmed = trim_session(session, session.minutes + 5)
    assert [e for e in all_exercises(trimmed)] == all_exercises(session)
    assert "ничего резать не пришлось" in trimmed.notes_ru[-1]


@pytest.mark.parametrize("minutes_left", [8, 12, 15, 20, 30, 40])
def test_a_trimmed_session_fits_the_window_it_was_given(minutes_left: int) -> None:
    session = prepare(home(KB16, DUMBBELLS), goal=Goal.FAT_LOSS, minutes=60)
    trimmed = trim_session(session, minutes_left)
    if trimmed.minutes > minutes_left:
        # The floor: the warm-up and one set of every main movement are never cut away.
        assert [b.kind for b in trimmed.blocks] == [BlockKind.WARMUP, BlockKind.MAIN]
        assert all(e.sets == 1 for e in block(trimmed, BlockKind.MAIN))


# --- symmetry -------------------------------------------------------------------------


@pytest.mark.parametrize(("left", "right", "counted"), [(8, 8, 8), (8, 6, 6), (5, 9, 5), (0, 4, 0)])
def test_both_sides_count_as_the_weaker_one(left: int, right: int, counted: int) -> None:
    assert matched_reps(left, right) == counted
