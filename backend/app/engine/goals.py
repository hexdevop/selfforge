"""What each goal asks of a workout (docs/01-domain.md, «Цели»)."""

from dataclasses import dataclass
from enum import StrEnum


class Goal(StrEnum):
    HYPERTROPHY = "hypertrophy"
    STRENGTH = "strength"
    ENDURANCE = "endurance"
    FAT_LOSS = "fat_loss"
    SKILL = "skill"
    HEALTH = "health"
    MAINTENANCE = "maintenance"


class Lever(StrEnum):
    """Ways to make the next session harder (docs/03-engine.md §2), plus the two outcomes
    that aren't a step forward."""

    REPS = "reps"
    WEIGHT = "weight"
    DIFFICULTY = "difficulty"
    UNILATERAL = "unilateral"
    TEMPO = "tempo"
    DENSITY = "density"
    VOLUME = "volume"
    ROLLBACK = "rollback"
    CEILING = "ceiling"


@dataclass(frozen=True)
class Scheme:
    sets: int
    reps: tuple[int, int]
    rest_seconds: int
    rir: int  # reps in reserve: how far from failure a set stops


@dataclass(frozen=True)
class GoalProfile:
    main: Scheme
    accessory: Scheme
    hold_seconds: tuple[int, int]  # target for timed exercises instead of reps
    min_rest_seconds: int  # the density lever never cuts rest below this
    max_sets: int  # the volume lever never adds sets above this
    levers: tuple[Lever, ...]  # tried in order once the top of the range is reached
    finisher: bool  # a short conditioning block at the end of the session


_STANDARD = (
    Lever.REPS,
    Lever.WEIGHT,
    Lever.DIFFICULTY,
    Lever.UNILATERAL,
    Lever.TEMPO,
    Lever.VOLUME,
)
_CONDITIONING = (
    Lever.REPS,
    Lever.WEIGHT,
    Lever.DENSITY,
    Lever.VOLUME,
    Lever.DIFFICULTY,
    Lever.TEMPO,
)

GOALS: dict[Goal, GoalProfile] = {
    Goal.STRENGTH: GoalProfile(
        main=Scheme(4, (3, 6), 180, 3),
        accessory=Scheme(3, (6, 10), 120, 2),
        hold_seconds=(15, 30),
        min_rest_seconds=120,
        max_sets=6,
        levers=_STANDARD,
        finisher=False,
    ),
    Goal.HYPERTROPHY: GoalProfile(
        main=Scheme(3, (8, 12), 90, 2),
        accessory=Scheme(3, (10, 15), 60, 1),
        hold_seconds=(20, 40),
        min_rest_seconds=60,
        max_sets=5,
        levers=_STANDARD,
        finisher=False,
    ),
    Goal.ENDURANCE: GoalProfile(
        main=Scheme(3, (15, 25), 45, 1),
        accessory=Scheme(2, (15, 25), 30, 1),
        hold_seconds=(30, 60),
        min_rest_seconds=20,
        max_sets=5,
        levers=_CONDITIONING,
        finisher=True,
    ),
    Goal.FAT_LOSS: GoalProfile(
        main=Scheme(3, (8, 15), 60, 1),
        accessory=Scheme(2, (12, 15), 45, 1),
        hold_seconds=(20, 45),
        min_rest_seconds=30,
        max_sets=4,
        levers=_CONDITIONING,
        finisher=True,
    ),
    # Until the skill tree (stage 5): strength through harder variations, far from failure.
    Goal.SKILL: GoalProfile(
        main=Scheme(4, (3, 6), 180, 4),
        accessory=Scheme(3, (5, 8), 120, 3),
        hold_seconds=(10, 20),
        min_rest_seconds=120,
        max_sets=5,
        levers=(Lever.REPS, Lever.DIFFICULTY, Lever.TEMPO),
        finisher=False,
    ),
    Goal.HEALTH: GoalProfile(
        main=Scheme(3, (8, 12), 75, 3),
        accessory=Scheme(2, (10, 12), 60, 3),
        hold_seconds=(20, 40),
        min_rest_seconds=60,
        max_sets=4,
        levers=_STANDARD,
        finisher=False,
    ),
    Goal.MAINTENANCE: GoalProfile(
        main=Scheme(3, (6, 12), 90, 2),
        accessory=Scheme(2, (8, 12), 60, 2),
        hold_seconds=(20, 40),
        min_rest_seconds=60,
        max_sets=4,
        levers=_STANDARD,
        finisher=False,
    ),
}
