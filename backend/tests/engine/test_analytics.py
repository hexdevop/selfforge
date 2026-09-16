from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.engine.analytics import (
    BodyWeight,
    LoggedSet,
    Period,
    ResultKind,
    Skill,
    SkillStatus,
    Target,
    best_result,
    body_mass_at,
    estimated_1rm,
    moving_average,
    near_records,
    pattern_progress,
    set_tonnage,
    side_imbalance,
    skill_state,
    tonnage_by_period,
    week_streak,
)
from tests.engine.catalog import BY_SLUG

D = Decimal
MSK = ZoneInfo("Europe/Moscow")
T0 = datetime(2026, 9, 7, 10, tzinfo=UTC)  # a Monday


def at(days: float = 0, hours: float = 0) -> datetime:
    return T0 + timedelta(days=days, hours=hours)


def logged(
    exercise: str,
    reps: int,
    *,
    session: str = "s1",
    index: int = 0,
    when: datetime = T0,
    weight: str | None = None,
    added: str | None = None,
    side: str = "both",
    warmup: bool = False,
) -> LoggedSet:
    return LoggedSet(
        session_id=session,
        exercise=exercise,
        set_index=index,
        performed_at=when,
        reps=reps,
        side=side,
        weight_kg=D(weight) if weight else None,
        added_weight_kg=D(added) if added else None,
        is_warmup=warmup,
    )


# --- estimated max --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("weight", "reps", "expected"),
    [
        ("100", 1, "100.00"),
        ("100", 10, "133.33"),
        ("16", 8, "20.27"),
        ("16", 11, None),  # past the range where Epley holds
        ("16", 0, None),
        ("0", 5, None),
    ],
)
def test_estimated_max_only_where_the_formula_holds(
    weight: str, reps: int, expected: str | None
) -> None:
    result = estimated_1rm(D(weight), reps)
    assert result == (D(expected) if expected else None)


# --- tonnage --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("set_", "body", "expected"),
    [
        (logged("goblet_squat", 10, weight="16"), "80", "720.00"),  # (16 + 0.7·80) × 10
        (logged("goblet_squat", 10, weight="16"), None, "160.00"),  # no weighing: load only
        (logged("pullup", 5), "80", "380.00"),  # 0.95 · 80 × 5
        (logged("weighted_pullup", 5, added="10"), "80", "430.00"),
        (logged("db_overhead_press", 10, weight="12"), "80", "120.00"),  # body doesn't travel
        (logged("farmer_carry", 40, weight="24"), "80", "0"),  # seconds, not reps
        (logged("pushup", 10, warmup=True), "80", "0"),
    ],
    ids=["loaded squat", "no weighing", "pullup", "weighted pullup", "press", "carry", "warmup"],
)
def test_set_tonnage(set_: LoggedSet, body: str | None, expected: str) -> None:
    exercise = BY_SLUG[set_.exercise]
    assert set_tonnage(set_, exercise, D(body) if body else None) == D(expected)


def test_body_mass_is_the_last_weighing_before_the_workout() -> None:
    weights = [BodyWeight(at(0), D("80")), BodyWeight(at(5), D("79"))]
    assert body_mass_at(at(3), weights) == D("80")
    assert body_mass_at(at(6), weights) == D("79")
    assert body_mass_at(at(-1), weights) == D("80")  # before any weighing: the first one
    assert body_mass_at(at(1), []) is None


def test_tonnage_by_week_uses_the_persons_time_zone() -> None:
    # Sunday 22:30 UTC is already Monday in Moscow.
    sunday_night = datetime(2026, 9, 13, 22, 30, tzinfo=UTC)
    sets = [
        logged("goblet_squat", 10, weight="16", when=at(0)),
        logged("goblet_squat", 10, weight="16", when=sunday_night),
    ]
    weeks = tonnage_by_period(sets, BY_SLUG, [], Period.WEEK, MSK)
    assert weeks == [(date(2026, 9, 7), D("160.00")), (date(2026, 9, 14), D("160.00"))]

    utc_weeks = tonnage_by_period(sets, BY_SLUG, [], Period.WEEK, UTC)
    assert utc_weeks == [(date(2026, 9, 7), D("320.00"))]


def test_tonnage_by_month_and_by_pattern() -> None:
    sets = [
        logged("goblet_squat", 10, weight="16", when=at(0)),
        logged("db_overhead_press", 10, weight="10", when=at(30)),
    ]
    months = tonnage_by_period(sets, BY_SLUG, [], Period.MONTH, UTC)
    assert months == [(date(2026, 9, 1), D("160.00")), (date(2026, 10, 1), D("100.00"))]
    squat_only = tonnage_by_period(sets, BY_SLUG, [], Period.WEEK, UTC, patterns={"squat"})
    assert squat_only == [(date(2026, 9, 7), D("160.00"))]


# --- body weight ----------------------------------------------------------------------


def test_weight_is_shown_as_a_seven_day_average() -> None:
    weights = [
        BodyWeight(at(0), D("80.0")),
        BodyWeight(at(1), D("81.0")),
        BodyWeight(at(6), D("79.0")),
        BodyWeight(at(7), D("78.0")),  # day 0 falls out of the window here
    ]
    assert moving_average(weights, UTC) == [
        (date(2026, 9, 7), D("80.00")),
        (date(2026, 9, 8), D("80.50")),
        (date(2026, 9, 13), D("80.00")),
        (date(2026, 9, 14), D("79.33")),
    ]


def test_two_weighings_on_one_day_make_one_point() -> None:
    weights = [BodyWeight(at(0, 1), D("80")), BodyWeight(at(0, 10), D("81"))]
    assert moving_average(weights, UTC) == [(date(2026, 9, 7), D("80.50"))]


# --- streak ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("workout_days", "today_offset", "expected"),
    [
        ([], 0, 0),
        ([0], 0, 1),
        ([0, 7, 14], 14, 3),
        ([0, 2, 4], 4, 1),  # three workouts in one week are still one week
        ([0, 7], 16, 2),  # this week has none yet: the streak holds
        ([0, 7], 21, 0),  # a whole week passed with nothing: the streak is over
        ([0, 14], 14, 1),  # a gap week in between
        ([6, 7], 7, 2),  # Sunday then Monday: two weeks
    ],
)
def test_week_streak(workout_days: list[int], today_offset: int, expected: int) -> None:
    workouts = [at(d) for d in workout_days]
    today = (T0 + timedelta(days=today_offset)).date()
    assert week_streak(workouts, today, UTC) == expected


# --- best results and pattern progress ------------------------------------------------


@pytest.mark.parametrize(
    ("sets", "exercise", "kind", "value"),
    [
        ([logged("goblet_squat", 8, weight="16")], "goblet_squat", ResultKind.EST_1RM, "20.27"),
        ([logged("pullup", 6), logged("pullup", 8, index=1)], "pullup", ResultKind.REPS, "8"),
        ([logged("plank", 45)], "plank", ResultKind.SECONDS, "45"),
        (
            [
                logged("split_squat", 10, side="left"),
                logged("split_squat", 7, side="right"),
            ],
            "split_squat",
            ResultKind.REPS,
            "7",  # the weaker side is what the set counts as
        ),
        (
            [
                logged("goblet_squat", 20, weight="8"),
                logged("goblet_squat", 5, index=1, weight="16"),
            ],
            "goblet_squat",
            ResultKind.EST_1RM,
            "18.67",  # the light 20-rep set can't be estimated and doesn't win
        ),
    ],
    ids=["loaded", "bodyweight", "timed", "one-sided", "high reps ignored"],
)
def test_best_result(sets: list[LoggedSet], exercise: str, kind: ResultKind, value: str) -> None:
    result = best_result(sets, BY_SLUG[exercise])
    assert result is not None
    assert (result.kind, result.value) == (kind, D(value))


def test_warmup_and_half_logged_sets_are_not_a_result() -> None:
    sets = [logged("pullup", 20, warmup=True), logged("split_squat", 10, side="left")]
    assert best_result(sets, BY_SLUG["pullup"]) is None
    assert best_result(sets, BY_SLUG["split_squat"]) is None


def test_pattern_progress_follows_the_ladder_without_breaking() -> None:
    sets = [
        logged("negative_pullup", 5, session="a", when=at(0)),
        logged("pullup", 2, session="b", when=at(7)),
        logged("negative_pullup", 6, session="b", index=1, when=at(7)),
        logged("pullup", 4, session="c", when=at(14)),
        logged("goblet_squat", 10, session="c", weight="16", when=at(14)),
    ]
    points = pattern_progress(sets, BY_SLUG, "pull_v", UTC)

    assert [(p.day, p.exercise) for p in points] == [
        (date(2026, 9, 7), "negative_pullup"),
        (date(2026, 9, 14), "pullup"),  # the hardest step of the day
        (date(2026, 9, 21), "pullup"),
    ]
    assert points[0].level < points[1].level
    assert [p.result.value if p.result else None for p in points] == [D(5), D(2), D(4)]


# --- side imbalance -------------------------------------------------------------------


def one_sided(left: int, right: int, days: float, index: int = 0) -> list[LoggedSet]:
    return [
        logged("split_squat", left, side="left", when=at(days), index=index, session=f"d{days}"),
        logged("split_squat", right, side="right", when=at(days), index=index, session=f"d{days}"),
    ]


@pytest.mark.parametrize(
    ("sets", "flagged"),
    [
        (one_sided(10, 10, 20), False),
        (one_sided(10, 9, 20), False),  # 10 % is normal variation
        (one_sided(10, 8, 20), True),  # 20 %
        (one_sided(10, 8, 1), False),  # older than four weeks from `now`
        (one_sided(10, 8, 20) + one_sided(10, 10, 21), False),  # 10 % on average
    ],
    ids=["even", "within 15%", "over 15%", "too old", "averaged out"],
)
def test_side_imbalance_over_four_weeks(sets: list[LoggedSet], flagged: bool) -> None:
    found = side_imbalance(sets, BY_SLUG, now=at(30))
    assert bool(found) is flagged
    if found:
        assert found[0].weaker_side == "right"
        assert "20%" in found[0].advice_ru
        assert "Правая" in found[0].advice_ru


def test_imbalance_ignores_two_sided_work_and_unfinished_sets() -> None:
    sets = [
        logged("pushup", 10, when=at(20)),
        logged("split_squat", 10, side="left", when=at(20)),  # right side not logged yet
    ]
    assert side_imbalance(sets, BY_SLUG, now=at(30)) == []


# --- skills ---------------------------------------------------------------------------

MUSCLE_UP = Skill(
    slug="muscle_up",
    goal=Target("muscle_up", reps=1),
    prerequisites=(Target("pullup", reps=10), Target("parallel_bar_dips", reps=12)),
    lead_ups=("pullup_pause", "weighted_pullup", "archer_pullup", "parallel_bar_dips"),
)


@pytest.mark.parametrize(
    ("sets", "marked", "status"),
    [
        ([], False, SkillStatus.LOCKED),
        ([logged("pullup", 10)], False, SkillStatus.LOCKED),
        (
            [logged("pullup", 10), logged("parallel_bar_dips", 12, index=1)],
            False,
            SkillStatus.IN_PROGRESS,
        ),
        ([logged("muscle_up", 1)], False, SkillStatus.ACHIEVED),
        ([], True, SkillStatus.ACHIEVED),
        (
            [logged("pullup", 12, warmup=True), logged("parallel_bar_dips", 12)],
            False,
            SkillStatus.LOCKED,
        ),
    ],
    ids=["nothing", "one prerequisite", "both prerequisites", "goal met", "marked", "warmup"],
)
def test_skill_status(sets: list[LoggedSet], marked: bool, status: SkillStatus) -> None:
    assert skill_state(MUSCLE_UP, sets, BY_SLUG, marked_achieved=marked).status is status


def test_skill_reports_how_far_each_prerequisite_is() -> None:
    state = skill_state(MUSCLE_UP, [logged("pullup", 7)], BY_SLUG)
    pullups, dips = state.prerequisites
    assert (pullups.best, pullups.met) == (7, False)
    assert (dips.best, dips.met) == (None, False)


def test_a_timed_skill_goal_counts_seconds() -> None:
    handstand = Skill("handstand", Target("wall_handstand_hold", hold_seconds=30), (), ("plank",))
    assert skill_state(handstand, [logged("wall_handstand_hold", 25)], BY_SLUG).status is (
        SkillStatus.IN_PROGRESS
    )
    assert skill_state(handstand, [logged("wall_handstand_hold", 30)], BY_SLUG).status is (
        SkillStatus.ACHIEVED
    )


def test_current_lead_up_is_the_one_done_most_recently() -> None:
    sets = [logged("archer_pullup", 3, when=at(0)), logged("pullup_pause", 5, when=at(3))]
    assert skill_state(MUSCLE_UP, sets, BY_SLUG).current_lead_up == "pullup_pause"
    assert skill_state(MUSCLE_UP, [], BY_SLUG).current_lead_up == "pullup_pause"


# --- near records ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("record", "last", "expected"),
    [
        (10, 9, "до рекорда 1 повтор"),
        (10, 10, None),  # equal is not "near", it's done
        (10, 11, None),  # a new record
        (10, 8, None),  # 80 % — not one good day away
    ],
)
def test_near_records(record: int, last: int, expected: str | None) -> None:
    sets = [
        logged("pullup", record, session="old", when=at(0)),
        logged("pullup", last, session="new", when=at(7)),
    ]
    found = near_records(sets, BY_SLUG, now=at(8))
    if expected is None:
        assert found == []
    else:
        assert len(found) == 1 and found[0].text_ru.endswith(expected)
