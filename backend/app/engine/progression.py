"""Six levers of progression and the rollback rule (docs/03-engine.md §2–3)."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal

from app.engine.goals import GOALS, Goal, GoalProfile, Lever
from app.engine.inventory import is_available, weight_grid
from app.engine.text import REPS, SECONDS, count, kg
from app.engine.types import CatalogExercise, Location

LOADED = ("barbell", "dumbbell", "kettlebell")
# eccentric-pause-concentric, seconds: first a slow lowering, then a pause at the bottom.
TEMPOS: tuple[str | None, ...] = (None, "3-0-1", "3-2-1")
ROLLBACK_AFTER = 3
DENSITY_STEP_SECONDS = 15


@dataclass(frozen=True)
class Prescription:
    exercise: str
    sets: int
    target: tuple[int, int]  # reps, or seconds for timed exercises
    rest_seconds: int
    weight_kg: Decimal | None = None
    tempo: str | None = None


@dataclass(frozen=True)
class Performance:
    """One session of an exercise: a number per working set. For one-sided work it is the
    weaker side — the symmetry rule makes it the one that counts."""

    prescription: Prescription
    done: tuple[int, ...]

    @property
    def topped(self) -> bool:
        p = self.prescription
        return len(self.done) >= p.sets and all(d >= p.target[1] for d in self.done)

    @property
    def failed(self) -> bool:
        """Below the bottom of the range on average."""
        p = self.prescription
        return sum(self.done) < p.sets * p.target[0]


@dataclass(frozen=True)
class ProgressionDecision:
    lever: Lever
    prescription: Prescription
    explanation_ru: str


def load_grid(exercise: CatalogExercise, location: Location) -> list[Decimal]:
    """Weights this exercise can be done with here; empty for bodyweight work."""
    grid: set[Decimal] = set()
    for group in exercise.required_equipment:
        for code in group:
            if code in LOADED and code in location.equipment:
                grid.update(weight_grid(location.equipment[code], pair=exercise.requires_pair))
    return sorted(grid)


@dataclass(frozen=True)
class _Context:
    current: Prescription
    exercise: CatalogExercise
    here: list[CatalogExercise]  # same pattern, doable at this location
    location: Location
    goal: GoalProfile

    @property
    def unit(self) -> tuple[str, str, str]:
        return SECONDS if self.exercise.timed else REPS

    def low(self, p: Prescription | None = None) -> str:
        """«8 повторов» — the bottom of the range, where a harder step starts."""
        target = (p or self.current).target
        return f"{target[0]} {self.unit[2]}"

    def switch(self, to: CatalogExercise) -> Prescription:
        grid = load_grid(to, self.location)
        weight = None
        if grid:
            weight = self.current.weight_kg if self.current.weight_kg in grid else grid[0]
        target = self.current.target
        if to.timed != self.exercise.timed:
            target = self.goal.hold_seconds if to.timed else self.goal.main.reps
        return replace(self.current, exercise=to.slug, weight_kg=weight, target=target, tempo=None)


def next_progression(
    history: Sequence[Performance],
    goal: Goal,
    location: Location,
    catalog: Sequence[CatalogExercise],
    health_flags: Collection[str] = (),
) -> ProgressionDecision:
    """What the next session of this exercise asks for. `history` is oldest first."""
    last = history[-1]
    exercise = next(e for e in catalog if e.slug == last.prescription.exercise)
    ctx = _Context(
        current=last.prescription,
        exercise=exercise,
        here=[
            e
            for e in catalog
            if e.pattern == exercise.pattern and is_available(e, location, health_flags)
        ],
        location=location,
        goal=GOALS[goal],
    )

    recent = [p for p in history if p.prescription.exercise == exercise.slug][-ROLLBACK_AFTER:]
    if len(recent) == ROLLBACK_AFTER and all(p.failed for p in recent):
        return _rollback(ctx)

    if not last.topped:
        top = ctx.current.target[1]
        step = "по несколько секунд" if exercise.timed else "по повтору"
        return ProgressionDecision(
            Lever.REPS,
            ctx.current,
            f"Цель — {count(top, ctx.unit)} в каждом подходе. "
            f"Прибавляй {step} там, где получается, остальное без изменений.",
        )

    for lever in ctx.goal.levers:
        step_up = _LEVERS.get(lever)
        if step_up and (decision := step_up(ctx)):
            return decision

    return ProgressionDecision(
        Lever.CEILING,
        ctx.current,
        f"«{exercise.title}» здесь упёрлось в потолок: тяжелее снаряда и сложнее варианта нет. "
        "Держим результат, а при пересборке программы подберём другое движение.",
    )


def _weight(ctx: _Context) -> ProgressionDecision | None:
    if ctx.current.weight_kg is None:
        return None
    heavier = [w for w in load_grid(ctx.exercise, ctx.location) if w > ctx.current.weight_kg]
    if not heavier:
        return None
    p = replace(ctx.current, weight_kg=heavier[0])
    return ProgressionDecision(
        Lever.WEIGHT,
        p,
        f"Верх диапазона взят во всех подходах — берём {kg(heavier[0])} "
        f"и начинаем снова с {ctx.low()}.",
    )


def _difficulty(ctx: _Context) -> ProgressionDecision | None:
    ex = ctx.exercise
    harder = next((e for e in ctx.here if e.slug == ex.next_slug), None)
    if harder is None:
        above = [e for e in ctx.here if ex.level < e.level <= ex.level + 2]
        harder = min(above, key=lambda e: (e.level, e.slug), default=None)
    if harder is None:
        return None
    p = ctx.switch(harder)
    no_heavier = ", а тяжелее снаряда здесь нет" if ctx.current.weight_kg is not None else ""
    return ProgressionDecision(
        Lever.DIFFICULTY,
        p,
        f"Верх диапазона взят{no_heavier}. Следующая ступень — «{harder.title}»: "
        f"начни с {ctx.low(p)}.",
    )


def _unilateral(ctx: _Context) -> ProgressionDecision | None:
    ex = ctx.exercise
    if ex.is_unilateral:
        return None
    loaded = bool(load_grid(ex, ctx.location))
    options = [e for e in ctx.here if e.is_unilateral and ex.level <= e.level <= ex.level + 1]
    if not options:
        return None
    one_side = min(
        options, key=lambda e: (bool(load_grid(e, ctx.location)) != loaded, e.level, e.slug)
    )
    p = ctx.switch(one_side)
    return ProgressionDecision(
        Lever.UNILATERAL,
        p,
        f"Дальше — работа на одну сторону: «{one_side.title}». Нагрузка на каждую сторону "
        f"почти вдвое больше без нового железа. Повторов на обе стороны поровну, "
        f"начни с {ctx.low(p)}.",
    )


def _tempo(ctx: _Context) -> ProgressionDecision | None:
    if ctx.exercise.timed or ctx.current.tempo not in TEMPOS[:-1]:
        return None
    tempo = TEMPOS[TEMPOS.index(ctx.current.tempo) + 1]
    how = (
        "добавь паузу 2 секунды в нижней точке — без отскока"
        if tempo == "3-2-1"
        else "опускайся медленно, за 3 секунды — с медленной фазой"
    )
    return ProgressionDecision(
        Lever.TEMPO,
        replace(ctx.current, tempo=tempo),
        f"Меняем темп: {how} та же нагрузка ощущается тяжелее. Начни с {ctx.low()}.",
    )


def _density(ctx: _Context) -> ProgressionDecision | None:
    old = ctx.current.rest_seconds
    rest = max(ctx.goal.min_rest_seconds, old - DENSITY_STEP_SECONDS)
    if rest >= old:
        return None
    return ProgressionDecision(
        Lever.DENSITY,
        replace(ctx.current, rest_seconds=rest),
        f"Отдых короче: {count(rest, SECONDS)} вместо {old}. Тот же объём за меньшее время.",
    )


def _volume(ctx: _Context) -> ProgressionDecision | None:
    sets = ctx.current.sets + 1
    if sets > ctx.goal.max_sets:
        return None
    return ProgressionDecision(
        Lever.VOLUME,
        replace(ctx.current, sets=sets),
        f"Добавляем подход: теперь их {sets}. Начни с {ctx.low()}.",
    )


_LEVERS = {
    Lever.WEIGHT: _weight,
    Lever.DIFFICULTY: _difficulty,
    Lever.UNILATERAL: _unilateral,
    Lever.TEMPO: _tempo,
    Lever.DENSITY: _density,
    Lever.VOLUME: _volume,
}


def _rollback(ctx: _Context) -> ProgressionDecision:
    why = (
        "Три тренировки подряд результат ниже нижней границы диапазона — так бывает: "
        "сон, стресс, накопленная усталость."
    )
    weight = ctx.current.weight_kg
    lighter = [w for w in load_grid(ctx.exercise, ctx.location) if weight and w < weight]
    if weight and lighter:
        # −10%, snapped to the nearest weight that exists.
        new = min(lighter, key=lambda w: abs(w - weight * Decimal("0.9")))
        return ProgressionDecision(
            Lever.ROLLBACK,
            replace(ctx.current, weight_kg=new),
            f"{why} Снижаем вес до {kg(new)}, чтобы вернуться в диапазон.",
        )

    ex = ctx.exercise
    easier = next((e for e in ctx.here if e.slug == ex.prev_slug), None)
    if easier is None:
        below = [e for e in ctx.here if e.level < ex.level]
        easier = max(below, key=lambda e: (e.level, e.slug), default=None)
    if easier is not None:
        return ProgressionDecision(
            Lever.ROLLBACK,
            ctx.switch(easier),
            f"{why} Шаг назад по лестнице: «{easier.title}». "
            f"К «{ex.title}» вернёмся, когда диапазон снова пойдёт.",
        )
    return ProgressionDecision(
        Lever.ROLLBACK,
        ctx.current,
        f"{why} Проще варианта здесь нет — оставляем как есть и смотрим по самочувствию.",
    )
