from decimal import Decimal

import pytest

from app.engine.goals import Goal
from app.engine.inventory import is_available
from app.engine.mesocycle import (
    COVERED,
    BlockKind,
    PlannedExercise,
    Program,
    ProgramInput,
    Structure,
    WeekKind,
    build_mesocycle,
    build_one_off_day,
)
from app.engine.types import Constraints, Equipment, Location, Surface
from app.seed import load_catalog
from tests.engine.catalog import BY_SLUG, CATALOG

D = Decimal

TITLES = {e.code: e.title_ru for e in load_catalog().equipment}
HOUSEHOLD = {code: Equipment(code) for code in ("chair", "sofa", "wall", "towel")}
KB16 = Equipment("kettlebell", weights_kg=(D(16),))


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
    title="Площадка у школы",
)

INTERMEDIATE = {
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
BEGINNER = dict.fromkeys(INTERMEDIATE, 1) | {"push_h": 2, "pull_v": 2, "pull_h": 2}


def build(
    *days: Location,
    goal: Goal = Goal.HYPERTROPHY,
    secondary: Goal | None = None,
    minutes: int = 45,
    levels: dict[str, int] = INTERMEDIATE,
    health: frozenset[str] = frozenset(),
    clearance: bool = False,
) -> Program:
    inp = ProgramInput(
        goal=goal,
        secondary_goal=secondary,
        session_minutes=minutes,
        levels=levels,
        day_locations=tuple(loc.id for loc in days),
        health_flags=health,
        needs_medical_clearance=clearance,
    )
    return build_mesocycle(inp, {loc.id: loc for loc in days}, CATALOG, TITLES)


def exercises(program: Program, location_id: str | None = None) -> list[PlannedExercise]:
    return [
        e
        for week in program.weeks
        for day in week.days
        if location_id in (None, day.location_id)
        for block in day.blocks
        for e in block.exercises
    ]


def slugs(program: Program, location_id: str | None = None) -> set[str]:
    return {e.exercise for e in exercises(program, location_id)}


def main_block(program: Program) -> list[PlannedExercise]:
    week = program.weeks[0]
    return [e for d in week.days for b in d.blocks if b.kind is BlockKind.MAIN for e in b.exercises]


def test_four_weeks_three_of_accumulation_then_a_deload() -> None:
    program = build(home(KB16), home(KB16), home(KB16))
    assert [w.kind for w in program.weeks] == [WeekKind.ACCUMULATION] * 3 + [WeekKind.DELOAD]
    first, deload = program.weeks[0], program.weeks[3]
    first_sets = [e.sets for d in first.days for b in d.blocks for e in b.exercises]
    deload_sets = [e.sets for d in deload.days for b in d.blocks for e in b.exercises]
    assert all(d < f for d, f in zip(deload_sets, first_sets, strict=True))
    peak_sets = [e.sets for d in program.weeks[2].days for b in d.blocks for e in b.exercises]
    assert sum(peak_sets) > sum(first_sets)


@pytest.mark.parametrize("minutes", [20, 30, 45, 60, 90])
@pytest.mark.parametrize("goal", list(Goal))
def test_every_session_fits_the_time_and_keeps_warmup_and_cooldown(
    goal: Goal, minutes: int
) -> None:
    program = build(home(KB16), PARK, home(KB16), goal=goal, minutes=minutes)
    for week in program.weeks:
        for day in week.days:
            assert day.minutes <= minutes, (goal, minutes, week.index, day.day_index)
            kinds = [b.kind for b in day.blocks]
            assert kinds[0] is BlockKind.WARMUP and kinds[-1] is BlockKind.COOLDOWN
            assert BlockKind.MAIN in kinds


def test_same_exercises_every_week_so_progression_has_something_to_track() -> None:
    program = build(home(KB16), PARK, home(KB16))
    per_week = [
        [e.exercise for d in w.days for b in d.blocks for e in b.exercises] for w in program.weeks
    ]
    assert all(week == per_week[0] for week in per_week)


def test_deterministic() -> None:
    assert build(home(KB16), PARK, home(KB16)) == build(home(KB16), PARK, home(KB16))


@pytest.mark.parametrize(
    ("days", "structure"),
    [
        (2, Structure.FULLBODY),
        (3, Structure.FULLBODY),
        (4, Structure.UPPER_LOWER),
        (5, Structure.PPL),
        (6, Structure.PPL),
    ],
)
def test_structure_follows_the_number_of_days(days: int, structure: Structure) -> None:
    assert build(*[home(KB16)] * days).structure is structure


def test_skill_stays_fullbody_whatever_the_days() -> None:
    program = build(*[PARK] * 5, goal=Goal.SKILL)
    assert program.structure is Structure.FULLBODY
    assert "навыки" in program.rationale_ru


def test_one_kettlebell_strength_three_days_home() -> None:
    location = home(KB16)
    program = build(location, location, location, goal=Goal.STRENGTH)
    assert program.structure is Structure.FULLBODY
    for e in exercises(program):
        assert is_available(BY_SLUG[e.exercise], location)
        assert not BY_SLUG[e.exercise].requires_pair
    assert all(e.target == (3, 6) and e.rest_seconds >= 180 for e in main_block(program))
    assert "Честно о силе" in program.rationale_ru
    assert "штанги" in program.rationale_ru


def test_strength_with_a_barbell_skips_the_warning() -> None:
    barbell = Equipment("barbell", bar_kg=D(20), plates=())
    program = build(home(barbell), home(barbell), goal=Goal.STRENGTH)
    assert "Честно о силе" not in program.rationale_ru


def test_one_dumbbell_beginner_without_pull_ups() -> None:
    location = home(Equipment("dumbbell", quantity=1, weights_kg=(D(10),)))
    program = build(location, location, location, levels=BEGINNER)
    assert not any(BY_SLUG[s].requires_pair for s in slugs(program))
    assert "one_arm_db_row" in slugs(program) or "towel_door_row" in slugs(program)
    # Nothing to pull down from at home: the program says so and what would help.
    assert not any(e.pattern == "pull_v" for e in exercises(program))
    assert "вертикальная тяга" in program.rationale_ru
    assert "турник" in program.rationale_ru


def test_four_days_two_at_the_park_split_upper_and_lower_by_place() -> None:
    house = home(KB16)
    program = build(house, PARK, house, PARK)
    week = program.weeks[0]
    assert {d.title for d in week.days if d.location_id == "park"} == {"Верх"}
    assert {d.title for d in week.days if d.location_id == "home"} == {"Низ"}
    pull_v_days = {d.location_id for d in week.days if "pull_v" in d.focus}
    assert pull_v_days == {"park"}
    assert "разных местах" in program.rationale_ru
    assert "Площадка у школы —" in program.rationale_ru


def test_one_kettlebell_and_a_park_becomes_an_explained_hybrid() -> None:
    house = home(KB16)
    program = build(house, PARK, house)
    week = program.weeks[0]
    assert all(d.title == "Всё тело" for d in week.days)
    park_day = next(d for d in week.days if d.location_id == "park")
    assert park_day.focus[0] == "pull_v"
    assert "фулбоди превратился в гибрид" in program.rationale_ru
    covered = {p for d in week.days for p in d.focus}
    assert covered >= set(COVERED)


def test_extras_that_fit_a_place_better_do_not_push_out_the_legs() -> None:
    # Carries need iron, so home beats the park for them — that alone must not cost a squat.
    house = home(KB16, Equipment("dumbbell", quantity=2, weights_kg=(D(8), D(10))), quiet_mode=True)
    week = build(
        house,
        PARK,
        house,
        goal=Goal.STRENGTH,
        secondary=Goal.HYPERTROPHY,
        levels=BEGINNER | {"push_h": 4, "squat": 2, "lunge": 2},
        health=frozenset({"knees"}),
    ).weeks[0]
    for day in week.days:
        if day.location_id == "home":
            assert {"squat", "lunge"} & set(day.focus), day.focus


def test_quiet_mode_has_no_jumps_rope_or_dropped_iron() -> None:
    location = home(KB16, Equipment("jump_rope"), quiet_mode=True)
    program = build(
        location, location, location, goal=Goal.FAT_LOSS, levels=INTERMEDIATE | {"cardio": 5}
    )
    assert any(b.kind is BlockKind.FINISHER for d in program.weeks[0].days for b in d.blocks)
    assert all(BY_SLUG[s].is_quiet for s in slugs(program))


def test_low_ceiling_has_no_standing_overhead_work() -> None:
    location = home(KB16, low_ceiling=True)
    program = build(location, location, levels=INTERMEDIATE | {"push_v": 4})
    assert not any(BY_SLUG[s].needs_ceiling_height for s in slugs(program))
    assert any(e.pattern == "push_v" for e in exercises(program))


def test_knee_restriction_picks_squats_from_safe_variants() -> None:
    location = home(KB16)
    program = build(
        location, location, levels=INTERMEDIATE | {"squat": 8}, health=frozenset({"knees"})
    )
    squats = [BY_SLUG[e.exercise] for e in exercises(program) if e.pattern == "squat"]
    assert squats
    assert not any("knees" in e.contraindicated_for for e in squats)
    assert "колени" in program.rationale_ru


def test_level_decides_the_step() -> None:
    advanced = build(PARK, PARK, PARK, levels=INTERMEDIATE | {"pull_v": 6})
    beginner = build(PARK, PARK, PARK, levels=INTERMEDIATE | {"pull_v": 2})
    assert "pullup" in slugs(advanced) or "chin_up" in slugs(advanced)
    assert "australian_pullup_high" in slugs(beginner)
    assert not {"pullup", "chin_up"} & slugs(beginner)


def test_goal_decides_the_scheme() -> None:
    endurance = build(home(KB16), home(KB16), goal=Goal.ENDURANCE)
    strength = build(home(KB16), home(KB16), goal=Goal.STRENGTH)
    assert all(e.target == (15, 25) and e.rest_seconds < 60 for e in main_block(endurance))
    assert all(e.target == (3, 6) and e.rest_seconds >= 180 for e in main_block(strength))


def test_secondary_goal_runs_the_accessories_and_can_add_a_finisher() -> None:
    program = build(home(KB16), home(KB16), minutes=60, secondary=Goal.ENDURANCE)
    blocks = program.weeks[0].days[0].blocks
    accessory = next(b for b in blocks if b.kind is BlockKind.ACCESSORY)
    assert all(e.target in ((15, 25), (30, 60)) for e in accessory.exercises)
    assert any(b.kind is BlockKind.FINISHER for b in blocks)
    assert "Второстепенная цель — выносливость" in program.rationale_ru


def test_short_sessions_say_what_did_not_fit() -> None:
    program = build(home(KB16), home(KB16), minutes=20, goal=Goal.STRENGTH)
    assert "За 20 минут всё не помещается" in program.rationale_ru


def test_medical_clearance_is_mentioned() -> None:
    assert "врачом" in build(home(KB16), home(KB16), clearance=True).rationale_ru
    assert "врачом" not in build(home(KB16), home(KB16)).rationale_ru


@pytest.mark.parametrize("minutes", [20, 45, 60])
@pytest.mark.parametrize("location", [home(KB16), PARK], ids=["home", "park"])
def test_a_one_off_day_is_a_full_workout_at_that_place(location: Location, minutes: int) -> None:
    inp = ProgramInput(
        goal=Goal.HYPERTROPHY,
        secondary_goal=None,
        session_minutes=minutes,
        levels=INTERMEDIATE,
        day_locations=("ignored", "ignored"),
    )
    day = build_one_off_day(inp, location, CATALOG)

    assert day.location_id == location.id
    assert day.minutes <= minutes
    kinds = [b.kind for b in day.blocks]
    assert kinds[0] is BlockKind.WARMUP and kinds[-1] is BlockKind.COOLDOWN
    exercises = [e for b in day.blocks for e in b.exercises]
    assert exercises
    assert all(is_available(BY_SLUG[e.exercise], location) for e in exercises)
    assert len({e.pattern for e in exercises}) >= (3 if minutes >= 45 else 2)
