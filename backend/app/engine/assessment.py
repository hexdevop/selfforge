"""Behavioural level assessment → starting step per pattern (docs/00-product.md).

We ask what people can do, not what they think of themselves. Only push-ups, pull-ups
and squats are asked directly; the rest is derived conservatively and corrected later
by progression. Numbers are positions on each pattern's difficulty scale (seed/).
"""

from dataclasses import dataclass
from enum import StrEnum


class Pushups(StrEnum):
    NONE = "0"
    FEW = "1-5"
    SOME = "6-15"
    MANY = "16-30"
    LOTS = "30+"


class Pullups(StrEnum):
    NONE = "0"
    FEW = "1-3"
    SOME = "4-8"
    MANY = "9-15"
    LOTS = "15+"


class Squats(StrEnum):
    UNDER_10 = "<10"
    UP_TO_25 = "10-25"
    UP_TO_50 = "25-50"
    OVER_50 = "50+"


class Pistol(StrEnum):
    NO = "no"
    ASSISTED = "assisted"
    YES = "yes"


class Overall(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class Answers:
    pushups: Pushups
    pullups: Pullups
    squats: Squats
    pistol: Pistol
    experienced: bool  # regular training 6+ months within the last year
    knows_terms: bool  # set, rep, failure, RIR


@dataclass(frozen=True)
class Assessment:
    levels: dict[str, int]
    guidance_level: str
    overall: Overall


# incline → knee → push-up → decline → archer
_PUSH_H = dict(zip(Pushups, (2, 3, 4, 5, 6), strict=True))
# australian (high) → negatives → pull-up → paused → weighted
_PULL_V = dict(zip(Pullups, (2, 5, 6, 7, 8), strict=True))
# box squat → air squat → paused → split squat
_SQUAT = dict(zip(Squats, (1, 2, 3, 4), strict=True))
_PISTOL = {Pistol.NO: 0, Pistol.ASSISTED: 7, Pistol.YES: 8}


def assess(answers: Answers, shift: int = 0) -> Assessment:
    """`shift` is the user's "lower / right / higher" answer to the summary: -1, 0 or +1."""
    push = _PUSH_H[answers.pushups]
    pull = _PULL_V[answers.pullups]
    squat = max(_SQUAT[answers.squats], _PISTOL[answers.pistol])

    levels = {
        "push_h": push,
        "pull_v": pull,
        "squat": squat,
        "push_v": 1 if push <= 3 else 3 if push <= 5 else 5,
        "core": 1 if push <= 3 else 2 if push <= 5 else 3,
        "pull_h": 2 if pull <= 5 else 4 if pull <= 7 else 6,
        "hinge": 1 if squat <= 2 else 2 if squat <= 4 else 3,
        "lunge": min(squat, 3) if squat <= 4 else 4,
        "carry": 1,
        "cardio": 3 if answers.experienced else 1,
    }
    levels = {pattern: max(1, level + shift) for pattern, level in levels.items()}

    # Position of each direct answer on a 0..4 scale.
    score = (
        list(Pushups).index(answers.pushups)
        + list(Pullups).index(answers.pullups)
        + list(Squats).index(answers.squats) * 4 / 3
    ) / 3
    overall = (
        Overall.BEGINNER if score < 1.5 else Overall.INTERMEDIATE if score < 3 else Overall.ADVANCED
    )

    guidance = "normal" if answers.experienced and answers.knows_terms else "verbose"
    return Assessment(levels=levels, guidance_level=guidance, overall=overall)
