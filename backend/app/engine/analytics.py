"""What grew and by how much (docs/03-engine.md §6–7)."""

from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.engine.text import REPS, SECONDS, count, kg
from app.engine.types import CatalogExercise

# Epley lies past this many reps, so no estimate is shown beyond it.
EST_1RM_MAX_REPS = 10
MOVING_AVERAGE_DAYS = 7
IMBALANCE_WEEKS = 4
IMBALANCE_THRESHOLD = Decimal("0.15")
# A record counts as within reach when the last result is at least this close to it.
NEAR_RECORD_SHARE = Decimal("0.9")

_CENT = Decimal("0.01")


class ResultKind(StrEnum):
    EST_1RM = "est_1rm"  # kilograms
    REPS = "reps"
    SECONDS = "seconds"


class Period(StrEnum):
    WEEK = "week"
    MONTH = "month"


class SkillStatus(StrEnum):
    LOCKED = "locked"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"


@dataclass(frozen=True)
class LoggedSet:
    session_id: str
    exercise: str
    set_index: int
    performed_at: datetime  # timezone-aware
    reps: int  # seconds of work for timed exercises
    side: str = "both"
    weight_kg: Decimal | None = None
    added_weight_kg: Decimal | None = None
    is_warmup: bool = False

    @property
    def load_kg(self) -> Decimal:
        return (self.weight_kg or Decimal(0)) + (self.added_weight_kg or Decimal(0))


@dataclass(frozen=True)
class BodyWeight:
    measured_at: datetime
    weight_kg: Decimal


def _round(value: Decimal) -> Decimal:
    return value.quantize(_CENT, ROUND_HALF_UP)


def estimated_1rm(weight_kg: Decimal, reps: int) -> Decimal | None:
    """Epley: `weight * (1 + reps / 30)`; nothing past 10 reps, where it stops being true."""
    if weight_kg <= 0 or not 1 <= reps <= EST_1RM_MAX_REPS:
        return None
    if reps == 1:
        return _round(weight_kg)
    return _round(weight_kg * (1 + Decimal(reps) / 30))


def body_mass_at(moment: datetime, weights: Sequence[BodyWeight]) -> Decimal | None:
    """The last weighing before `moment`; the first one if the workout came earlier."""
    before = [w for w in weights if w.measured_at <= moment]
    if before:
        return max(before, key=lambda w: w.measured_at).weight_kg
    return min(weights, key=lambda w: w.measured_at).weight_kg if weights else None


def set_tonnage(
    logged: LoggedSet, exercise: CatalogExercise, body_mass_kg: Decimal | None
) -> Decimal:
    """Kilograms moved by one set: external load plus the exercise's share of body mass.

    Timed work and warm-up sets move nothing that counts. Without a weighing the body share
    is left out rather than guessed.
    """
    if logged.is_warmup or exercise.timed or logged.reps <= 0:
        return Decimal(0)
    body = exercise.bodyweight_share * body_mass_kg if body_mass_kg else Decimal(0)
    return _round((logged.load_kg + body) * logged.reps)


def period_start(moment: datetime, period: Period, tz: tzinfo) -> date:
    """Monday of the week, or the first of the month, in the person's own time zone."""
    day = moment.astimezone(tz).date()
    if period is Period.WEEK:
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def tonnage_by_period(
    sets: Iterable[LoggedSet],
    catalog: Mapping[str, CatalogExercise],
    weights: Sequence[BodyWeight],
    period: Period,
    tz: tzinfo,
    patterns: Collection[str] | None = None,
) -> list[tuple[date, Decimal]]:
    totals: dict[date, Decimal] = defaultdict(Decimal)
    for s in sets:
        exercise = catalog.get(s.exercise)
        if exercise is None or (patterns is not None and exercise.pattern not in patterns):
            continue
        tonnage = set_tonnage(s, exercise, body_mass_at(s.performed_at, weights))
        totals[period_start(s.performed_at, period, tz)] += tonnage
    return sorted(totals.items())


def moving_average(
    weights: Sequence[BodyWeight], tz: tzinfo, days: int = MOVING_AVERAGE_DAYS
) -> list[tuple[date, Decimal]]:
    """One point per day with a weighing: the mean of that day's trailing `days` window.

    Daily weight jumps by a kilogram on water alone; the average is what's worth looking at.
    """
    by_day: dict[date, list[Decimal]] = defaultdict(list)
    for w in weights:
        by_day[w.measured_at.astimezone(tz).date()].append(w.weight_kg)

    points = []
    for day in sorted(by_day):
        window = [
            value
            for other, values in by_day.items()
            if day - timedelta(days=days - 1) <= other <= day
            for value in values
        ]
        points.append((day, _round(sum(window, Decimal(0)) / len(window))))
    return points


def week_streak(workouts: Iterable[datetime], today: date, tz: tzinfo) -> int:
    """Weeks in a row with at least one workout, ending now.

    The current week isn't over, so a week without a workout yet doesn't break the streak —
    it just isn't counted until one happens.
    """
    weeks = {period_start(w, Period.WEEK, tz) for w in workouts}
    week = today - timedelta(days=today.weekday())
    if week not in weeks:
        week -= timedelta(weeks=1)
    streak = 0
    while week in weeks:
        streak += 1
        week -= timedelta(weeks=1)
    return streak


def _working_sets(sets: Iterable[LoggedSet]) -> dict[tuple[str, str, int], list[LoggedSet]]:
    """Working sets grouped as the person did them: one entry per side of the same set."""
    grouped: dict[tuple[str, str, int], list[LoggedSet]] = defaultdict(list)
    for s in sets:
        if not s.is_warmup:
            grouped[(s.session_id, s.exercise, s.set_index)].append(s)
    return grouped


def _counted_reps(sides: Sequence[LoggedSet], unilateral: bool) -> int | None:
    """What a set counts as: the weaker side (§6); a one-sided set with a side missing
    doesn't count yet."""
    if not unilateral:
        return max(s.reps for s in sides)
    by_side = {s.side: s.reps for s in sides}
    if "left" in by_side and "right" in by_side:
        return min(by_side["left"], by_side["right"])
    return by_side.get("both")


@dataclass(frozen=True)
class Result:
    kind: ResultKind
    value: Decimal

    def text(self) -> str:
        if self.kind is ResultKind.EST_1RM:
            return f"расчётный максимум {kg(self.value)}"
        return count(int(self.value), SECONDS if self.kind is ResultKind.SECONDS else REPS)


def _kind(exercise: CatalogExercise, loaded: bool) -> ResultKind:
    if exercise.timed:
        return ResultKind.SECONDS
    return ResultKind.EST_1RM if loaded else ResultKind.REPS


def best_result(sets: Iterable[LoggedSet], exercise: CatalogExercise) -> Result | None:
    """The best set of these: estimated max where there was load, else reps or seconds.

    Once an exercise is done with load, loaded sets are what's compared — a light high-rep
    set doesn't count as a better result than a heavy one.
    """
    candidates: list[tuple[Decimal, int]] = []
    for sides in _working_sets(s for s in sets if s.exercise == exercise.slug).values():
        reps = _counted_reps(sides, exercise.is_unilateral)
        if reps:
            candidates.append((sides[0].load_kg, reps))
    if not candidates:
        return None

    if not exercise.timed:
        estimates = [e for load, reps in candidates if (e := estimated_1rm(load, reps))]
        if estimates:
            return Result(ResultKind.EST_1RM, max(estimates))
        if any(load > 0 for load, _ in candidates):
            # Loaded, but every set was past the range Epley can be trusted in.
            return None
    kind = _kind(exercise, loaded=False)
    return Result(kind, Decimal(max(reps for _, reps in candidates)))


def best_reps(sets: Iterable[LoggedSet], exercise: CatalogExercise) -> int | None:
    """Most reps (or seconds) in one working set, whatever the load — for skill goals."""
    counted = [
        reps
        for sides in _working_sets(s for s in sets if s.exercise == exercise.slug).values()
        if (reps := _counted_reps(sides, exercise.is_unilateral))
    ]
    return max(counted, default=None)


@dataclass(frozen=True)
class ProgressPoint:
    session_id: str
    day: date
    exercise: str
    level: int
    result: Result | None


def pattern_progress(
    sets: Iterable[LoggedSet],
    catalog: Mapping[str, CatalogExercise],
    pattern: str,
    tz: tzinfo,
) -> list[ProgressPoint]:
    """One point per workout that trained `pattern`: the hardest step done and its best set.

    Progress is followed by pattern, not by exercise, so moving to the next step of the
    ladder continues the line instead of starting a new one.
    """
    by_session: dict[str, list[LoggedSet]] = defaultdict(list)
    for s in sets:
        exercise = catalog.get(s.exercise)
        if exercise is not None and exercise.pattern == pattern and not s.is_warmup:
            by_session[s.session_id].append(s)

    points = []
    for session_id, session_sets in by_session.items():
        done = {catalog[s.exercise] for s in session_sets}
        hardest = max(done, key=lambda e: (e.level, e.slug))
        points.append(
            ProgressPoint(
                session_id=session_id,
                day=min(s.performed_at for s in session_sets).astimezone(tz).date(),
                exercise=hardest.slug,
                level=hardest.level,
                result=best_result(session_sets, hardest),
            )
        )
    return sorted(points, key=lambda p: (p.day, p.session_id))


@dataclass(frozen=True)
class Imbalance:
    exercise: str
    weaker_side: str
    left_avg: Decimal
    right_avg: Decimal
    gap: Decimal  # share of the stronger side, 0.2 = 20 %
    advice_ru: str


_SIDE_NAMES = {"left": "Левая", "right": "Правая"}


def side_imbalance(
    sets: Iterable[LoggedSet],
    catalog: Mapping[str, CatalogExercise],
    now: datetime,
    weeks: int = IMBALANCE_WEEKS,
    threshold: Decimal = IMBALANCE_THRESHOLD,
) -> list[Imbalance]:
    """One-sided exercises where one side averaged over 15 % fewer reps in the last 4 weeks.

    Only sets with both sides logged are compared, so an unfinished set doesn't read as a gap.
    """
    since = now - timedelta(weeks=weeks)
    sides: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for group in _working_sets(s for s in sets if s.performed_at >= since).values():
        exercise = catalog.get(group[0].exercise)
        if exercise is None or not exercise.is_unilateral:
            continue
        by_side = {s.side: s.reps for s in group}
        if "left" in by_side and "right" in by_side:
            sides[exercise.slug]["left"].append(by_side["left"])
            sides[exercise.slug]["right"].append(by_side["right"])

    found = []
    for slug, reps in sorted(sides.items()):
        left = _round(Decimal(sum(reps["left"])) / len(reps["left"]))
        right = _round(Decimal(sum(reps["right"])) / len(reps["right"]))
        stronger = max(left, right)
        if stronger == 0:
            continue
        gap = _round((stronger - min(left, right)) / stronger)
        if gap <= threshold:
            continue
        weaker = "left" if left < right else "right"
        percent = int((gap * 100).quantize(Decimal(1), ROUND_HALF_UP))
        found.append(
            Imbalance(
                exercise=slug,
                weaker_side=weaker,
                left_avg=left,
                right_avg=right,
                gap=gap,
                advice_ru=(
                    f"{_SIDE_NAMES[weaker]} сторона в среднем делает на {percent}% меньше. "
                    "Так бывает почти у всех. Начинай подход с неё и добавь ей один подход "
                    "в конце — сильная сторона пусть равняется на слабую, а не наоборот."
                ),
            )
        )
    return found


@dataclass(frozen=True)
class Target:
    exercise: str
    reps: int | None = None
    hold_seconds: int | None = None

    @property
    def needed(self) -> int:
        return self.reps if self.reps is not None else self.hold_seconds or 0


@dataclass(frozen=True)
class Skill:
    slug: str
    goal: Target | None
    prerequisites: tuple[Target, ...]
    lead_ups: tuple[str, ...]


@dataclass(frozen=True)
class TargetProgress:
    target: Target
    best: int | None

    @property
    def met(self) -> bool:
        return self.best is not None and self.best >= self.target.needed


@dataclass(frozen=True)
class SkillState:
    skill: str
    status: SkillStatus
    goal: TargetProgress | None
    prerequisites: tuple[TargetProgress, ...]
    current_lead_up: str


def skill_state(
    skill: Skill,
    sets: Sequence[LoggedSet],
    catalog: Mapping[str, CatalogExercise],
    marked_achieved: bool = False,
) -> SkillState:
    """Locked until the prerequisites are met, achieved once the goal is — or when the
    person says so, for skills the catalog can't check."""

    def progress(target: Target) -> TargetProgress:
        exercise = catalog.get(target.exercise)
        return TargetProgress(target, best_reps(sets, exercise) if exercise else None)

    goal = progress(skill.goal) if skill.goal else None
    prerequisites = tuple(progress(p) for p in skill.prerequisites)
    if marked_achieved or (goal is not None and goal.met):
        status = SkillStatus.ACHIEVED
    elif all(p.met for p in prerequisites):
        status = SkillStatus.IN_PROGRESS
    else:
        status = SkillStatus.LOCKED

    last_done = {s.exercise: s.performed_at for s in sorted(sets, key=lambda s: s.performed_at)}
    done_lead_ups = [slug for slug in skill.lead_ups if slug in last_done]
    current = (
        max(done_lead_ups, key=lambda slug: last_done[slug]) if done_lead_ups else skill.lead_ups[0]
    )
    return SkillState(skill.slug, status, goal, prerequisites, current)


@dataclass(frozen=True)
class NearRecord:
    exercise: str
    record: Result
    last: Result
    text_ru: str


def near_records(
    sets: Sequence[LoggedSet],
    catalog: Mapping[str, CatalogExercise],
    now: datetime,
    weeks: int = IMBALANCE_WEEKS,
) -> list[NearRecord]:
    """Exercises whose last workout came within 10 % of the best result ever: a record
    that's one good day away."""
    recent = {s.exercise for s in sets if s.performed_at >= now - timedelta(weeks=weeks)}
    found = []
    for slug in sorted(recent):
        exercise = catalog.get(slug)
        if exercise is None:
            continue
        mine = [s for s in sets if s.exercise == slug]
        last_session = max(mine, key=lambda s: s.performed_at).session_id
        last = best_result([s for s in mine if s.session_id == last_session], exercise)
        earlier = best_result([s for s in mine if s.session_id != last_session], exercise)
        if (
            last is None
            or earlier is None
            or last.kind is not earlier.kind
            or last.value >= earlier.value
            or last.value < earlier.value * NEAR_RECORD_SHARE
        ):
            continue
        gap = earlier.value - last.value
        if last.kind is ResultKind.EST_1RM:
            left = f"{kg(_round(gap))} расчётного максимума"
        else:
            left = count(int(gap), SECONDS if last.kind is ResultKind.SECONDS else REPS)
        title = f"«{exercise.title}»" if exercise.title else slug
        found.append(NearRecord(slug, earlier, last, f"{title}: до рекорда {left}"))
    return found
