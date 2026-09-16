"""Building a four-week mesocycle (docs/03-engine.md §4)."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from itertools import permutations
from math import ceil

from app.engine.goals import GOALS, Goal, Scheme
from app.engine.inventory import is_available
from app.engine.patterns import main_line
from app.engine.progression import load_grid
from app.engine.text import (
    GOAL_NAMES,
    HEALTH_NAMES,
    KIND_NAMES,
    PATTERN_NAMES,
    REPS,
    SETS,
    WORKOUTS,
    count,
    duration,
    listing,
    plural,
)
from app.engine.types import CatalogExercise, Location


class Structure(StrEnum):
    FULLBODY = "fullbody"
    UPPER_LOWER = "upper_lower"
    PPL = "ppl"


class WeekKind(StrEnum):
    ACCUMULATION = "accumulation"
    DELOAD = "deload"


class BlockKind(StrEnum):
    WARMUP = "warmup"
    MAIN = "main"
    ACCESSORY = "accessory"
    FINISHER = "finisher"
    COOLDOWN = "cooldown"


# Volume builds for three weeks, then a deload: fewer sets at the same intensity.
WEEKS = (
    (WeekKind.ACCUMULATION, Decimal("1.0")),
    (WeekKind.ACCUMULATION, Decimal("1.1")),
    (WeekKind.ACCUMULATION, Decimal("1.2")),
    (WeekKind.DELOAD, Decimal("0.6")),
)

# Patterns a week should cover; carry and cardio are extras.
COVERED = ("squat", "hinge", "push_h", "push_v", "pull_h", "pull_v", "lunge", "core")
_NEVER_MAIN = ("core", "carry")
_MAIN_SLOTS = 2
SECONDS_PER_REP = 3
SETUP_SECONDS = 60  # moving between exercises, setting up the implement
_FINISHER = Scheme(sets=3, reps=(30, 45), rest_seconds=30, rir=1)  # seconds of work


def exercise_seconds(sets: int, top: int, timed: bool, unilateral: bool, rest_seconds: int) -> int:
    """Seconds an exercise takes, counting the top of the range and both sides."""
    work = top if timed else top * SECONDS_PER_REP
    return sets * work * (2 if unilateral else 1) + (sets - 1) * rest_seconds + SETUP_SECONDS


@dataclass(frozen=True)
class ProgramInput:
    goal: Goal
    secondary_goal: Goal | None
    session_minutes: int
    levels: Mapping[str, int]  # pattern → position on its difficulty scale
    day_locations: tuple[str, ...]  # location id for each training day, in order
    health_flags: frozenset[str] = frozenset()
    needs_medical_clearance: bool = False


@dataclass(frozen=True)
class PlannedExercise:
    exercise: str
    pattern: str
    sets: int
    target: tuple[int, int]  # reps, or seconds when `timed`
    timed: bool
    rest_seconds: int
    rir: int
    tempo: str | None = None


@dataclass(frozen=True)
class Block:
    kind: BlockKind
    minutes: int
    exercises: tuple[PlannedExercise, ...] = ()


@dataclass(frozen=True)
class PlannedDay:
    day_index: int
    location_id: str
    title: str
    focus: tuple[str, ...]
    minutes: int
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class Week:
    index: int
    kind: WeekKind
    volume_multiplier: Decimal
    days: tuple[PlannedDay, ...]


@dataclass(frozen=True)
class Program:
    goal: Goal
    structure: Structure
    weeks: tuple[Week, ...]
    rationale_ru: str


@dataclass(frozen=True)
class _Template:
    title: str
    patterns: tuple[str, ...]  # by priority


_UPPER = _Template("Верх", ("push_h", "pull_v", "push_v", "pull_h", "core", "carry"))
_LOWER = _Template("Низ", ("squat", "hinge", "lunge", "core", "carry"))
_PUSH = _Template("Жим", ("push_h", "push_v", "core"))
_PULL = _Template("Тяга", ("pull_v", "pull_h", "carry", "core"))
_LEGS = _Template("Ноги", ("squat", "hinge", "lunge", "core"))


def _structure(goal: Goal, days: int) -> Structure:
    if days <= 3 or goal is Goal.SKILL:
        return Structure.FULLBODY
    return Structure.UPPER_LOWER if days == 4 else Structure.PPL


def _templates(structure: Structure, days: int) -> list[_Template]:
    if structure is Structure.UPPER_LOWER:
        return [_UPPER, _LOWER] * 2
    if structure is Structure.PPL:
        return [_PUSH, _PULL, _LEGS, _PUSH, _PULL, _LEGS][:days]
    result = []
    for k in range(days):
        # Swap the pair members every other day so a short week still touches every pattern.
        flip = 1 if k % 2 == 0 else -1
        knee, knee2 = ("squat", "lunge")[::flip]
        push, push2 = ("push_h", "push_v")[::flip]
        pull, pull2 = ("pull_v", "pull_h")[::flip]
        patterns = (knee, push, pull, "hinge", "core", pull2, push2, knee2, "carry")
        result.append(_Template("Всё тело", patterns))
    return result


def _round_sets(sets: int, multiplier: Decimal) -> int:
    return max(1, int((sets * multiplier).quantize(Decimal(1), ROUND_HALF_UP)))


@dataclass
class _Day:
    """A training day being filled. The same exercises repeat every week of the cycle."""

    index: int
    template: _Template
    location_id: str
    order: list[str]  # the template's patterns, re-prioritised for this place
    budget: int  # seconds still free for exercises
    main: list[PlannedExercise] = field(default_factory=list)
    accessory: list[PlannedExercise] = field(default_factory=list)
    finisher: list[PlannedExercise] = field(default_factory=list)

    @property
    def patterns(self) -> set[str]:
        return {p.pattern for p in self.main + self.accessory}


class _Planner:
    def __init__(
        self,
        inp: ProgramInput,
        locations: Mapping[str, Location],
        catalog: Sequence[CatalogExercise],
        equipment_titles: Mapping[str, str],
    ) -> None:
        self.inp = inp
        self.goal = GOALS[inp.goal]
        self.accessory_goal = GOALS[inp.secondary_goal or inp.goal]
        self.locations = locations
        self.catalog = catalog
        self.by_slug = {e.slug: e for e in catalog}
        self.main_line = {
            e.slug
            for pattern in PATTERN_NAMES
            for e in main_line(x for x in catalog if x.pattern == pattern)
        }
        self.equipment_titles = equipment_titles
        self.week_locations = list(dict.fromkeys(inp.day_locations))
        self.here = {
            loc_id: [e for e in catalog if is_available(e, locations[loc_id], inp.health_flags)]
            for loc_id in self.week_locations
        }
        self.fits = {
            (pattern, loc_id): self._fit(pattern, loc_id)
            for pattern in PATTERN_NAMES
            for loc_id in self.week_locations
        }
        warmup, cooldown = (5, 3) if inp.session_minutes >= 30 else (3, 2)
        self.warmup, self.cooldown = warmup, cooldown
        self.budget = (inp.session_minutes - warmup - cooldown) * 60

    def level(self, pattern: str) -> int:
        return self.inp.levels.get(pattern, 1)

    def pick(
        self, pattern: str, loc_id: str, exclude: Sequence[str] = ()
    ) -> CatalogExercise | None:
        """The hardest step not above the person's level (one above if nothing fits),
        preferring the iron that's there, reps over holds, two-sided work, the main line."""
        level = self.level(pattern)
        location = self.locations[loc_id]
        options = [
            e
            for e in self.here[loc_id]
            if e.pattern == pattern and e.level <= level + 1 and e.slug not in exclude
        ]

        def rank(e: CatalogExercise) -> tuple[bool, int, bool, bool, bool, bool, str]:
            fits = e.level <= level
            return (
                fits,
                e.level if fits else -e.level,
                bool(load_grid(e, location)),
                not e.timed,
                not e.is_unilateral,
                e.slug in self.main_line,
                e.slug,
            )

        return max(options, key=rank, default=None)

    def fit(self, pattern: str, loc_id: str) -> int:
        return self.fits[pattern, loc_id]

    def _fit(self, pattern: str, loc_id: str) -> int:
        """How well a place serves a pattern: 0 nothing, 1 only a regression, 2 bodyweight
        at level, 3 loaded at level."""
        e = self.pick(pattern, loc_id)
        if e is None:
            return 0
        if e.level < self.level(pattern) - 1:
            return 1
        return 3 if load_grid(e, self.locations[loc_id]) else 2

    def assign(self, templates: list[_Template]) -> list[_Template]:
        """Give each day the template its place serves best; ties keep the usual order."""
        if len(self.week_locations) == 1:
            return templates

        def score(order: Iterable[_Template]) -> int:
            return sum(
                self.fit(p, loc)
                for t, loc in zip(order, self.inp.day_locations, strict=True)
                for p in t.patterns[:4]
            )

        return list(max(permutations(templates), key=score))

    def order(self, patterns: tuple[str, ...], loc_id: str) -> list[str]:
        """Patterns another place of the week serves better go last; main patterns this place
        serves best go first. Core and carry keep their spot: an extra that happens to fit
        here better must not push a squat out of the day."""
        others = [loc for loc in self.week_locations if loc != loc_id]
        if not others:
            return list(patterns)

        def rank(p: str) -> int:
            here, elsewhere = self.fit(p, loc_id), max(self.fit(p, o) for o in others)
            if here < elsewhere:
                return 2
            return 0 if here > elsewhere and p not in _NEVER_MAIN else 1

        return sorted(patterns, key=rank)

    def cost(self, p: PlannedExercise, sets: int | None = None) -> int:
        return exercise_seconds(
            sets=p.sets if sets is None else sets,
            top=p.target[1],
            timed=p.timed,
            unilateral=self.by_slug[p.exercise].is_unilateral,
            rest_seconds=p.rest_seconds,
        )

    def add(self, day: _Day, pattern: str, lead: bool) -> bool:
        """Put an exercise for `pattern` into the day if there is one here and time for it."""
        used = [p.exercise for p in day.main + day.accessory]
        e = self.pick(pattern, day.location_id, used)
        if e is None:
            return False
        is_main = lead and len(day.main) < _MAIN_SLOTS and pattern not in _NEVER_MAIN
        goal = self.goal if is_main else self.accessory_goal
        scheme = goal.main if is_main else goal.accessory
        planned = PlannedExercise(
            exercise=e.slug,
            pattern=e.pattern,
            sets=scheme.sets,
            target=goal.hold_seconds if e.timed else scheme.reps,
            timed=e.timed,
            rest_seconds=scheme.rest_seconds,
            rir=scheme.rir,
        )
        spend = self.cost(planned)
        if (day.main or day.accessory) and spend > day.budget:
            return False
        day.budget -= spend
        (day.main if is_main else day.accessory).append(planned)
        return True

    def plan_day(self, index: int, template: _Template, loc_id: str) -> _Day:
        day = _Day(index, template, loc_id, self.order(template.patterns, loc_id), self.budget)
        wants_finisher = self.goal.finisher or (
            self.inp.secondary_goal is not None and self.accessory_goal.finisher
        )
        if wants_finisher and (e := self.pick("cardio", loc_id)):
            # A finisher is timed work, whatever the exercise normally counts.
            s = _FINISHER
            finisher = PlannedExercise(
                e.slug, e.pattern, s.sets, s.reps, True, s.rest_seconds, s.rir
            )
            day.finisher.append(finisher)
            day.budget -= self.cost(finisher)
        for pattern in day.order:
            self.add(day, pattern, lead=True)
        return day

    def cover(self, days: list[_Day]) -> None:
        """A pattern no day's template reached gets one slot where it's served best."""
        for pattern in COVERED:
            if any(pattern in d.patterns for d in days):
                continue
            best = max(self.fit(pattern, d.location_id) for d in days)
            candidates = [d for d in days if self.fit(pattern, d.location_id) == best]
            for day in sorted(candidates, key=lambda d: -d.budget):
                if best and self.add(day, pattern, lead=False):
                    break

    def week(self, days: list[_Day], index: int, kind: WeekKind, m: Decimal) -> Week:
        planned = []
        for d in days:
            exercises = d.main + d.accessory + d.finisher
            sets = [p.sets for p in exercises]
            if m < 1:
                sets = [_round_sets(s, m) for s in sets]
            else:
                # Add the week's extra sets main exercises first, as long as the session fits.
                for i, p in enumerate(exercises):
                    trial = [*sets[:i], _round_sets(p.sets, m), *sets[i + 1 :]]
                    total = sum(self.cost(x, s) for x, s in zip(exercises, trial, strict=True))
                    if total <= self.budget:
                        sets = trial
            scaled = [replace(p, sets=s) for p, s in zip(exercises, sets, strict=True)]

            blocks = [Block(BlockKind.WARMUP, self.warmup)]
            start = 0
            for block_kind, part in (
                (BlockKind.MAIN, d.main),
                (BlockKind.ACCESSORY, d.accessory),
                (BlockKind.FINISHER, d.finisher),
            ):
                chunk = scaled[start : start + len(part)]
                start += len(part)
                if chunk:
                    seconds = sum(self.cost(p) for p in chunk)
                    blocks.append(Block(block_kind, ceil(seconds / 60), tuple(chunk)))
            blocks.append(Block(BlockKind.COOLDOWN, self.cooldown))

            work = ceil(sum(self.cost(p) for p in scaled) / 60)
            planned.append(
                PlannedDay(
                    day_index=d.index,
                    location_id=d.location_id,
                    title=d.template.title,
                    focus=tuple(dict.fromkeys(p.pattern for p in d.main + d.accessory)),
                    minutes=self.warmup + work + self.cooldown,
                    blocks=tuple(blocks),
                )
            )
        return Week(index, kind, m, tuple(planned))

    def build(self) -> Program:
        inp = self.inp
        structure = _structure(inp.goal, len(inp.day_locations))
        templates = self.assign(_templates(structure, len(inp.day_locations)))
        days = [
            self.plan_day(i, t, loc)
            for i, (t, loc) in enumerate(zip(templates, inp.day_locations, strict=True))
        ]
        self.cover(days)
        # Time still left: a second exercise for each day's lead patterns.
        for day in days:
            for pattern in day.order[:2]:
                self.add(day, pattern, lead=False)

        weeks = tuple(self.week(days, i, kind, m) for i, (kind, m) in enumerate(WEEKS))
        return Program(inp.goal, structure, weeks, self.rationale(structure, days))

    def rationale(self, structure: Structure, days: list[_Day]) -> str:
        inp = self.inp
        workouts = f"{count(len(days), WORKOUTS)} в неделю"
        paragraphs = []

        if inp.goal is Goal.SKILL:
            paragraphs.append(
                f"Цель — навыки, поэтому {workouts} строятся как фулбоди на сложных вариантах "
                "движений: мало повторов, полный отдых, подходы далеко от отказа. Сила растёт "
                "через освоение следующих ступеней лестницы."
            )
        elif structure is Structure.FULLBODY:
            paragraphs.append(
                f"{workouts.capitalize()} — это фулбоди: каждое занятие нагружает всё тело, "
                "и каждое движение получает работу несколько раз за неделю."
            )
        elif structure is Structure.UPPER_LOWER:
            paragraphs.append(
                f"{workouts.capitalize()} — верх и низ по очереди: каждая группа мышц "
                "работает дважды в неделю и успевает восстановиться."
            )
        else:
            paragraphs.append(
                f"{workouts.capitalize()} — жим, тяга и ноги по очереди: за занятие работает "
                "одна группа движений, остальные в это время восстанавливаются."
            )

        if len(self.week_locations) > 1:
            by_place = {
                loc: set().union(*(d.patterns for d in days if d.location_id == loc))
                for loc in self.week_locations
            }
            lines = []
            for loc, patterns in by_place.items():
                elsewhere = set().union(*(p for o, p in by_place.items() if o != loc))
                only_here = [PATTERN_NAMES[p] for p in COVERED if p in patterns - elsewhere]
                if only_here:
                    location = self.locations[loc]
                    name = location.title or KIND_NAMES[location.kind]
                    lines.append(f"{name} — {listing(only_here)}.")
            if lines:
                hybrid = "фулбоди превратился в гибрид: " if structure is Structure.FULLBODY else ""
                paragraphs.append(
                    f"Тренировки проходят в разных местах, поэтому {hybrid}каждое движение "
                    "отдано туда, где для него есть снаряды. " + " ".join(lines)
                )

        if inp.goal is Goal.STRENGTH and not any(
            "barbell" in self.locations[loc].equipment for loc in self.week_locations
        ):
            paragraphs.append(
                "Честно о силе: без штанги классическую силу в приседе и тяге не построить. "
                "Поэтому сила здесь растёт через сложность движения — пистолетик, отжимания "
                "на одной руке, подтягивания с весом. Мерило — освоенная ступень, а не килограммы."
            )

        trained = set().union(*(d.patterns for d in days))
        missing = [p for p in COVERED if p not in trained]
        no_gear = [p for p in missing if all(self.fit(p, d.location_id) == 0 for d in days)]
        no_time = [p for p in missing if p not in no_gear]
        if no_gear:
            text = (
                f"Без упражнений остались: {listing([PATTERN_NAMES[p] for p in no_gear])} — "
                "в выбранных местах для этого нет снарядов."
            )
            if hints := self.gear_hints(no_gear):
                text += f" Подойдёт, например: {listing(hints, 'или')}."
            paragraphs.append(text)
        if no_time:
            paragraphs.append(
                f"За {inp.session_minutes} минут всё не помещается, поэтому без отдельной работы "
                f"остались: {listing([PATTERN_NAMES[p] for p in no_time])}."
            )

        if inp.health_flags:
            tags = [HEALTH_NAMES[t] for t in HEALTH_NAMES if t in inp.health_flags]
            paragraphs.append(
                f"Учтены ограничения ({', '.join(tags)}): варианты, которые их нагружают, "
                "в программу не попадают."
            )

        main = self.goal.main
        paragraphs.append(
            f"Основные упражнения — {count(main.sets, SETS)} по {main.reps[0]}–{main.reps[1]} "
            f"{plural(main.reps[1], REPS)}, отдых между подходами — "
            f"{duration(main.rest_seconds)}. Подход заканчивай, когда в запасе "
            f"остаётся {count(main.rir, REPS)}."
        )
        if inp.secondary_goal:
            paragraphs.append(
                f"Второстепенная цель — {GOAL_NAMES[inp.secondary_goal]}: вспомогательные "
                "упражнения идут в её режиме."
            )
        if any(d.finisher for d in days):
            paragraphs.append("В конце тренировки — короткий финишер на пульс.")

        paragraphs.append(
            "Недели 1–3 — накопление: объём понемногу растёт. Неделя 4 — разгрузочная: "
            "подходов меньше, нагрузка та же. Это часть плана — так восстановление "
            "успевает за нагрузкой."
        )
        if inp.needs_medical_clearance:
            paragraphs.append(
                "По ответам на старте перед нагрузками стоит посоветоваться с врачом."
            )
        return "\n\n".join(paragraphs)

    def gear_hints(self, patterns: list[str]) -> list[str]:
        """Equipment that would open the most steps of these patterns near the person's level."""
        owned = {code for loc in self.week_locations for code in self.locations[loc].equipment}
        opens: dict[str, int] = {}
        for pattern in patterns:
            level = self.level(pattern)
            for e in sorted(self.catalog, key=lambda e: (e.level, e.slug)):
                if (
                    e.pattern == pattern
                    and level - 1 <= e.level <= level + 3
                    and not e.contraindicated_for & self.inp.health_flags
                ):
                    for code in {c for group in e.required_equipment for c in group} - owned:
                        opens[code] = opens.get(code, 0) + 1
        best = sorted(opens, key=lambda c: -opens[c])
        titles = [self.equipment_titles[c] for c in best if c in self.equipment_titles][:3]
        return [t[0].lower() + t[1:] for t in titles]


def build_mesocycle(
    inp: ProgramInput,
    locations: Mapping[str, Location],
    catalog: Sequence[CatalogExercise],
    equipment_titles: Mapping[str, str] | None = None,
) -> Program:
    """Four weeks of planned sessions for these days and places, with the reasons in Russian.

    `locations` must contain every id in `inp.day_locations`.
    """
    return _Planner(inp, locations, catalog, equipment_titles or {}).build()
