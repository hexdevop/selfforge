"""Preparing and reshaping one workout (docs/03-engine.md §5–6)."""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from math import ceil

from app.engine.goals import GOALS, Goal, Lever
from app.engine.inventory import is_available
from app.engine.mesocycle import BlockKind, PlannedDay, PlannedExercise, exercise_seconds
from app.engine.progression import Performance, load_grid, next_progression
from app.engine.text import REPS, SECONDS, count, kg, listing
from app.engine.types import CatalogExercise, Location


class Feeling(StrEnum):
    """One of the three taps before a session. `GOOD` means slept well, calm, not sore."""

    BAD = "bad"
    OK = "ok"
    GOOD = "good"


class SubstitutionReason(StrEnum):
    EQUIPMENT_BUSY = "equipment_busy"
    PAIN = "pain"
    TOO_HARD = "too_hard"
    TOO_EASY = "too_easy"
    DISLIKED = "disliked"


_POINTS = {Feeling.BAD: 1, Feeling.OK: 2, Feeling.GOOD: 3}
# Readiness 3..9 points → volume multiplier, the 0.7–1.1 band of docs/03-engine.md §3.
_VOLUME = (
    Decimal("0.7"),
    Decimal("0.8"),
    Decimal("0.9"),
    Decimal("1.0"),
    Decimal("1.05"),
    Decimal("1.1"),
    Decimal("1.1"),
)


@dataclass(frozen=True)
class Readiness:
    sleep: Feeling = Feeling.OK
    stress: Feeling = Feeling.OK
    soreness: Feeling = Feeling.OK

    @property
    def points(self) -> int:
        return _POINTS[self.sleep] + _POINTS[self.stress] + _POINTS[self.soreness]

    @property
    def volume_multiplier(self) -> Decimal:
        return _VOLUME[self.points - 3]


@dataclass(frozen=True)
class Drill:
    """A warm-up or cool-down movement: no load, no progression, measured in seconds."""

    title_ru: str
    seconds: int


@dataclass(frozen=True)
class SessionExercise:
    exercise: str
    pattern: str
    sets: int
    target: tuple[int, int]  # reps, or seconds of work when `timed`
    timed: bool
    rest_seconds: int
    rir: int
    unilateral: bool
    weight_kg: Decimal | None = None
    tempo: str | None = None
    hint_ru: str = ""  # why this weight and this target
    # The slot this fills: the slug the plan was generated with. Progression follows the
    # slot, so a lever that moves a slot up the ladder keeps its history.
    planned_slug: str = ""

    @property
    def seconds(self) -> int:
        return exercise_seconds(
            self.sets, self.target[1], self.timed, self.unilateral, self.rest_seconds
        )


@dataclass(frozen=True)
class SessionBlock:
    kind: BlockKind
    minutes: int
    exercises: tuple[SessionExercise, ...] = ()
    drills: tuple[Drill, ...] = ()


@dataclass(frozen=True)
class Session:
    blocks: tuple[SessionBlock, ...]
    volume_multiplier: Decimal
    notes_ru: tuple[str, ...] = ()

    @property
    def minutes(self) -> int:
        return sum(b.minutes for b in self.blocks)


_GENERAL_WARMUP = (
    Drill("Суставная разминка сверху вниз: шея, плечи, таз, колени", 90),
    Drill("Разгон пульса: быстрая ходьба или шаги на месте", 60),
)
_PATTERN_WARMUP = {
    "squat": Drill("Приседания без веса в полный диапазон", 45),
    "hinge": Drill("Наклоны с прямой спиной, ладони скользят по бёдрам", 45),
    "push_h": Drill("Отжимания от опоры, медленное опускание", 45),
    "push_v": Drill("Круги руками и подъёмы рук над головой", 45),
    "pull_h": Drill("Сведение лопаток и тяга к себе без веса", 45),
    "pull_v": Drill("Вис или подтягивание лопаток вниз", 45),
    "lunge": Drill("Выпады на месте без веса, по очереди на каждую ногу", 45),
    "core": Drill("Планка на локтях", 30),
    "carry": Drill("Проход с напряжённым корпусом, плечи вниз", 30),
    "cardio": Drill("Лёгкий бег или шаги на месте", 60),
}
_COOLDOWN = (
    Drill("Спокойное дыхание: вдох на 4 счёта, выдох на 6", 60),
    Drill("Растяжка поработавших мышц до лёгкого натяжения, без боли", 120),
)


def _minutes(exercises: Sequence[SessionExercise]) -> int:
    return ceil(sum(e.seconds for e in exercises) / 60)


def _fit(drills: Sequence[Drill], minutes: int) -> tuple[Drill, ...]:
    """As many drills as the block's minutes hold, in order; at least one."""
    budget = minutes * 60
    kept: list[Drill] = []
    for drill in drills:
        if kept and drill.seconds > budget:
            continue
        budget -= drill.seconds
        kept.append(drill)
    return tuple(kept)


def warmup_drills(patterns: Sequence[str], minutes: int) -> tuple[Drill, ...]:
    """General part first, then one drill per pattern the day actually trains."""
    specific = [_PATTERN_WARMUP[p] for p in dict.fromkeys(patterns) if p in _PATTERN_WARMUP]
    return _fit([*_GENERAL_WARMUP, *specific], minutes)


def matched_reps(left: int, right: int) -> int:
    """Symmetry rule (§6): both sides count as the weaker one — the strong side does not
    catch up, the weak one is what the next session is built on."""
    return min(left, right)


def prepare_session(
    planned: PlannedDay,
    history: Mapping[str, Sequence[Performance]],
    readiness: Readiness,
    location: Location,
    catalog: Sequence[CatalogExercise],
    goal: Goal,
    health_flags: Collection[str] = (),
) -> Session:
    """Turn this week's plan into a session with concrete weights.

    `history` maps a planned exercise slug to what was actually done in that slot, oldest
    first. Its last entry may name a different exercise: a progression lever can move a slot
    up the ladder while the plan keeps the slug it was generated with.
    """
    by_slug = {e.slug: e for e in catalog}
    multiplier = readiness.volume_multiplier
    blocks: list[SessionBlock] = []

    for block in planned.blocks:
        if block.kind is BlockKind.WARMUP:
            blocks.append(
                SessionBlock(
                    block.kind, block.minutes, drills=warmup_drills(planned.focus, block.minutes)
                )
            )
            continue
        if block.kind is BlockKind.COOLDOWN:
            blocks.append(SessionBlock(block.kind, block.minutes, drills=_fit(_COOLDOWN, 3)))
            continue
        exercises = tuple(
            _prepare(
                planned=p,
                past=history.get(p.exercise, ()),
                location=location,
                catalog=catalog,
                by_slug=by_slug,
                goal=goal,
                health_flags=health_flags,
            )
            for p in block.exercises
        )
        if exercises:
            blocks.append(SessionBlock(block.kind, _minutes(exercises), exercises))

    scaled = _scale_volume(blocks, multiplier, goal)
    prepared = Session(tuple(scaled), multiplier, _readiness_notes(readiness))
    # The plan names exercises for the place it was built for; today may be somewhere else.
    return swap_location(prepared, location, catalog, goal, health_flags)


def _scale_volume(
    blocks: Sequence[SessionBlock], multiplier: Decimal, goal: Goal
) -> list[SessionBlock]:
    """Move the session's total set count towards `multiplier`.

    Readiness scales volume, not each exercise separately — rounding every exercise on its
    own leaves a 1.05 day unchanged and a 0.9 day cut twice. Below one the finisher goes
    first and then accessory sets; the main movements are never touched. Above one the extra
    sets land on accessory work first.
    """
    if multiplier == 1:
        return list(blocks)

    planned_total = sum(e.sets for b in blocks for e in b.exercises)
    target = max(1, int((planned_total * multiplier).quantize(Decimal(1), ROUND_HALF_UP)))

    if multiplier < 1:
        blocks = [b for b in blocks if b.kind is not BlockKind.FINISHER]
        order = [
            (bi, ei)
            for bi, b in enumerate(blocks)
            if b.kind is BlockKind.ACCESSORY
            for ei in reversed(range(len(b.exercises)))
        ][::-1]
        step, floor = -1, 1
    else:
        order = [
            (bi, ei)
            for kind in (BlockKind.ACCESSORY, BlockKind.MAIN, BlockKind.FINISHER)
            for bi, b in enumerate(blocks)
            if b.kind is kind
            for ei in range(len(b.exercises))
        ]
        step, floor = 1, GOALS[goal].max_sets

    sets = {(bi, ei): e.sets for bi, b in enumerate(blocks) for ei, e in enumerate(b.exercises)}
    total = sum(sets.values())
    moved = True
    while moved and (total > target if step < 0 else total < target):
        moved = False
        for key in order:
            if total == target:
                break
            if (sets[key] > floor) if step < 0 else (sets[key] < floor):
                sets[key] += step
                total += step
                moved = True

    return [
        SessionBlock(b.kind, b.minutes, b.exercises, b.drills)
        if not b.exercises
        else _rebuild(b, [replace(e, sets=sets[bi, ei]) for ei, e in enumerate(b.exercises)])
        for bi, b in enumerate(blocks)
    ]


def _rebuild(block: SessionBlock, exercises: Sequence[SessionExercise]) -> SessionBlock:
    return SessionBlock(block.kind, _minutes(exercises), tuple(exercises), block.drills)


def _readiness_notes(readiness: Readiness) -> tuple[str, ...]:
    if readiness.volume_multiplier < 1:
        return (
            "Готовность сегодня ниже обычной. Основные движения оставил как есть, "
            "вспомогательный объём срезал — так тренировка всё равно считается.",
        )
    if readiness.volume_multiplier > 1:
        return ("Готовность высокая — добавил немного объёма во вспомогательных движениях.",)
    return ()


def _prepare(
    *,
    planned: PlannedExercise,
    past: Sequence[Performance],
    location: Location,
    catalog: Sequence[CatalogExercise],
    by_slug: Mapping[str, CatalogExercise],
    goal: Goal,
    health_flags: Collection[str],
) -> SessionExercise:
    sets = planned.sets
    slug, target = planned.exercise, planned.target
    rest, tempo = planned.rest_seconds, planned.tempo
    weight: Decimal | None = None
    hint = ""

    # A performance of an exercise this place can't host (the slot was done elsewhere, at
    # home in the rain) can't drive progression here: it would prescribe that exercise again.
    past = [
        perf
        for perf in past
        if (done := by_slug.get(perf.prescription.exercise)) is not None
        and is_available(done, location, health_flags)
    ]
    if past:
        decision = next_progression(past, goal, location, catalog, health_flags)
        p = decision.prescription
        slug, target, rest, tempo, weight = (
            p.exercise,
            p.target,
            p.rest_seconds,
            p.tempo,
            p.weight_kg,
        )
        hint = decision.explanation_ru
        if decision.lever is Lever.VOLUME:
            sets = max(sets, p.sets)
    else:
        grid = load_grid(by_slug[slug], location)
        weight = grid[0] if grid else None
        hint = _first_time(by_slug[slug], target[0], weight)

    exercise = by_slug[slug]
    return SessionExercise(
        exercise=slug,
        pattern=exercise.pattern,
        sets=sets,
        target=target,
        timed=exercise.timed,
        rest_seconds=rest,
        rir=planned.rir,
        unilateral=exercise.is_unilateral,
        weight_kg=weight,
        tempo=tempo,
        hint_ru=hint,
        planned_slug=planned.exercise,
    )


def _first_time(exercise: CatalogExercise, low: int, weight: Decimal | None) -> str:
    unit = SECONDS if exercise.timed else REPS
    start = f"начинаем с {kg(weight)} и " if weight is not None else "ориентир — "
    return (
        f"Первый раз в этом движении: {start}{count(low, unit)} в подходе. "
        "По тому, как пройдёт, подберём нагрузку на следующий раз."
    )


def _shares_equipment(a: CatalogExercise, b: CatalogExercise) -> bool:
    codes = {code for group in b.required_equipment for code in group}
    return any(code in codes for group in a.required_equipment for code in group)


def substitute_exercise(
    current: SessionExercise,
    reason: SubstitutionReason,
    location: Location,
    catalog: Sequence[CatalogExercise],
    goal: Goal,
    used: Collection[str] = (),
    health_flags: Collection[str] = (),
) -> SessionExercise | None:
    """A replacement for the same pattern from what is doable here and now, or None."""
    by_slug = {e.slug: e for e in catalog}
    exercise = by_slug[current.exercise]
    here = [
        e
        for e in catalog
        if e.pattern == exercise.pattern
        and e.slug != exercise.slug
        and e.slug not in used
        and is_available(e, location, health_flags)
    ]
    if not here:
        return None

    wanted = exercise.level
    if reason is SubstitutionReason.TOO_HARD:
        wanted = exercise.level - 1
        here = [e for e in here if e.level < exercise.level] or here
    elif reason is SubstitutionReason.TOO_EASY:
        wanted = exercise.level + 1
        here = [e for e in here if e.level > exercise.level] or here

    def rank(e: CatalogExercise) -> tuple[bool, int, str]:
        # A busy implement is the point of the swap: anything else comes first.
        busy = reason is SubstitutionReason.EQUIPMENT_BUSY and _shares_equipment(e, exercise)
        return (busy, abs(e.level - wanted), e.slug)

    pick = min(here, key=rank)
    grid = load_grid(pick, location)
    weight: Decimal | None = None
    if grid:
        lighter = [w for w in grid if current.weight_kg is None or w <= current.weight_kg]
        weight = lighter[-1] if lighter else grid[0]

    target = current.target
    if pick.timed != current.timed:
        target = GOALS[goal].hold_seconds if pick.timed else GOALS[goal].main.reps

    return SessionExercise(
        exercise=pick.slug,
        pattern=pick.pattern,
        sets=current.sets,
        target=target,
        timed=pick.timed,
        rest_seconds=current.rest_seconds,
        rir=current.rir,
        unilateral=pick.is_unilateral,
        weight_kg=weight,
        tempo=None,
        hint_ru=_substitution_hint(reason, pick),
        planned_slug=current.planned_slug,
    )


def _substitution_hint(reason: SubstitutionReason, pick: CatalogExercise) -> str:
    name = f"«{pick.title}»" if pick.title else "другой вариант"
    if reason is SubstitutionReason.EQUIPMENT_BUSY:
        return f"Снаряд занят — берём {name}: то же движение, другое оборудование."
    if reason is SubstitutionReason.PAIN:
        return (
            f"Меняем на {name} — тот же паттерн в более щадящем варианте. "
            "Боль — сигнал остановиться, а не потерпеть: если она остаётся, пропусти движение."
        )
    if reason is SubstitutionReason.TOO_HARD:
        return f"Ступень ниже — {name}. Вернёмся к прежнему, когда диапазон пойдёт увереннее."
    if reason is SubstitutionReason.TOO_EASY:
        return f"Ступень выше — {name}: прежний вариант перестал быть нагрузкой."
    return f"Заменил на {name} — тот же паттерн. Повторные замены учтём при пересборке программы."


_CUTTABLE = (BlockKind.ACCESSORY, BlockKind.FINISHER)


def trim_session(session: Session, minutes_left: int) -> Session:
    """Rebuild what is left of the session to fit `minutes_left`.

    Warm-up is never cut. Accessory work and the finisher go first, then the cool-down;
    the main movements stay and only lose sets when there is nothing else to drop.
    """
    warmup = [b for b in session.blocks if b.kind is BlockKind.WARMUP]
    cooldown = next((b for b in session.blocks if b.kind is BlockKind.COOLDOWN), None)
    main = [e for b in session.blocks if b.kind is BlockKind.MAIN for e in b.exercises]
    extras = [(b.kind, e) for b in session.blocks if b.kind in _CUTTABLE for e in b.exercises]

    def assemble(
        kept_extras: Sequence[tuple[BlockKind, SessionExercise]],
        kept_main: Sequence[SessionExercise],
        keep_cooldown: bool,
    ) -> list[SessionBlock]:
        blocks = list(warmup)
        if kept_main:
            blocks.append(SessionBlock(BlockKind.MAIN, _minutes(kept_main), tuple(kept_main)))
        for kind in _CUTTABLE:
            chunk = tuple(e for k, e in kept_extras if k == kind)
            if chunk:
                blocks.append(SessionBlock(kind, _minutes(chunk), chunk))
        if keep_cooldown and cooldown is not None:
            blocks.append(cooldown)
        return blocks

    # Cut in the order the plan can afford to lose things, re-measuring after every step:
    # a block's minutes are rounded up, so seconds alone would miss the window by a minute.
    kept_extras, kept_main, keep_cooldown = list(extras), list(main), True
    blocks = assemble(kept_extras, kept_main, keep_cooldown)
    while sum(b.minutes for b in blocks) > minutes_left:
        if kept_extras:
            kept_extras.pop()
        elif keep_cooldown:
            keep_cooldown = False
        elif any(e.sets > 1 for e in kept_main):
            i = max(range(len(kept_main)), key=lambda i: (kept_main[i].sets, i))
            kept_main[i] = replace(kept_main[i], sets=kept_main[i].sets - 1)
        else:
            break  # warm-up plus one set of every main movement is the floor
        blocks = assemble(kept_extras, kept_main, keep_cooldown)

    dropped = len(extras) - len(kept_extras)
    cut_sets = sum(a.sets - b.sets for a, b in zip(main, kept_main, strict=True))
    return Session(
        tuple(blocks),
        session.volume_multiplier,
        (*session.notes_ru, _trim_note(dropped, cut_sets, minutes_left)),
    )


def _trim_note(dropped: int, cut_sets: int, minutes_left: int) -> str:
    what = []
    if dropped:
        what.append("убрал вспомогательные движения")
    if cut_sets:
        what.append("срезал подходы в основных")
    if not what:
        return (
            f"Всё, что осталось, укладывается в {minutes_left} минут — ничего резать не пришлось."
        )
    return (
        f"Уложил остаток в {minutes_left} минут: {listing(what)}. "
        "Главные движения дня остались на месте — тренировка засчитана."
    )


def swap_location(
    session: Session,
    location: Location,
    catalog: Sequence[CatalogExercise],
    goal: Goal,
    health_flags: Collection[str] = (),
    done: Collection[str] = (),
) -> Session:
    """The same session at another place: the same patterns, other equipment.

    What this place can host stays; everything else becomes the closest step of the same
    pattern that can be done here. `done` — exercises with sets already logged — stay as
    they are: what was done is history, not a plan to rebuild.
    """
    by_slug = {e.slug: e for e in catalog}
    here = [e for e in catalog if is_available(e, location, health_flags)]
    used = {e.exercise for b in session.blocks for e in b.exercises}
    swapped: list[tuple[str, str]] = []
    dropped: list[str] = []

    def rebuild(current: SessionExercise) -> SessionExercise | None:
        exercise = by_slug[current.exercise]
        if current.exercise in done or exercise in here:
            weight = _snap(current.weight_kg, load_grid(exercise, location))
            return replace(current, weight_kg=weight) if current.exercise not in done else current
        options = [e for e in here if e.pattern == exercise.pattern and e.slug not in used]
        if not options:
            dropped.append(exercise.title or exercise.slug)
            return None
        # Closest in difficulty; on a tie the easier one — unfamiliar equipment is enough.
        pick = min(options, key=lambda e: (abs(e.level - exercise.level), e.level, e.slug))
        used.add(pick.slug)
        swapped.append((exercise.title or exercise.slug, pick.title or pick.slug))
        target = current.target
        if pick.timed != current.timed:
            target = GOALS[goal].hold_seconds if pick.timed else GOALS[goal].main.reps
        return replace(
            current,
            exercise=pick.slug,
            pattern=pick.pattern,
            target=target,
            timed=pick.timed,
            unilateral=pick.is_unilateral,
            weight_kg=_snap(current.weight_kg, load_grid(pick, location)),
            tempo=None,
            hint_ru=(
                f"Вместо «{exercise.title or exercise.slug}» — то же движение под то, "
                f"что есть здесь."
            ),
        )

    blocks: list[SessionBlock] = []
    for block in session.blocks:
        if not block.exercises:
            blocks.append(block)
            continue
        kept = [e for e in (rebuild(x) for x in block.exercises) if e is not None]
        if kept:
            blocks.append(_rebuild(block, kept))

    if not swapped and not dropped:
        return replace(session, blocks=tuple(blocks))
    return Session(
        tuple(blocks),
        session.volume_multiplier,
        (*session.notes_ru, _swap_note(location, swapped, dropped)),
    )


def _snap(weight: Decimal | None, grid: Sequence[Decimal]) -> Decimal | None:
    """The heaviest weight here not above the one planned; the lightest if all are above."""
    if not grid:
        return None
    if weight is None:
        return grid[0]
    lighter = [w for w in grid if w <= weight]
    return lighter[-1] if lighter else grid[0]


def _swap_note(location: Location, swapped: list[tuple[str, str]], dropped: list[str]) -> str:
    place = f"«{location.title}»" if location.title else "это место"
    parts = [f"Тренировка собрана под {place}."]
    if swapped:
        parts.append("Заменил: " + "; ".join(f"{was} → {now}" for was, now in swapped) + ".")
    if dropped:
        parts.append(
            f"Здесь нечем заменить: {listing(dropped)} — сегодня без них, "
            "остальная тренировка на месте."
        )
    return " ".join(parts)
