import pytest

from app.engine.assessment import Answers, Overall, Pistol, Pullups, Pushups, Squats, assess
from app.engine.patterns import main_line, step_at
from app.schemas.catalog import PatternCode
from tests.engine.catalog import pattern_exercises


def answers(
    pushups: Pushups = Pushups.SOME,
    pullups: Pullups = Pullups.SOME,
    squats: Squats = Squats.UP_TO_25,
    pistol: Pistol = Pistol.NO,
    experienced: bool = False,
    knows_terms: bool = False,
) -> Answers:
    return Answers(pushups, pullups, squats, pistol, experienced, knows_terms)


def start(result_levels: dict[str, int], pattern: str) -> str:
    return step_at(main_line(pattern_exercises(pattern)), result_levels[pattern]).slug


@pytest.mark.parametrize(
    ("given", "expected_steps", "overall"),
    [
        pytest.param(
            answers(Pushups.NONE, Pullups.NONE, Squats.UNDER_10),
            {
                "push_h": "incline_pushup",
                "pull_v": "australian_pullup_high",
                "squat": "box_squat",
                "pull_h": "towel_door_row",
                "push_v": "band_overhead_press",
                "core": "dead_bug",
                "hinge": "glute_bridge",
                "lunge": "step_up",
                "carry": "goblet_carry",
            },
            Overall.BEGINNER,
            id="complete beginner starts at the bottom everywhere",
        ),
        pytest.param(
            answers(Pushups.MANY, Pullups.NONE, Squats.UP_TO_50),
            {
                "push_h": "decline_pushup",
                "pull_v": "australian_pullup_high",
                "squat": "pause_squat",
                "push_v": "pike_pushup",
                "core": "plank",
            },
            Overall.INTERMEDIATE,
            id="typical home trainee: plenty of push-ups, zero pull-ups",
        ),
        pytest.param(
            answers(Pushups.LOTS, Pullups.LOTS, Squats.OVER_50, Pistol.YES),
            {
                "push_h": "archer_pushup",
                "pull_v": "weighted_pullup",
                "squat": "pistol_squat",
                "pull_h": "archer_ring_row",
                "push_v": "elevated_pike_pushup",
                "lunge": "walking_lunge",
            },
            Overall.ADVANCED,
            id="strong all round",
        ),
        pytest.param(
            answers(Pushups.FEW, Pullups.SOME, Squats.UNDER_10, Pistol.ASSISTED),
            {"squat": "assisted_pistol", "pull_v": "pullup"},
            Overall.BEGINNER,
            id="pistol answer overrides the rep count",
        ),
    ],
)
def test_assessment_lands_on_the_right_steps(
    given: Answers, expected_steps: dict[str, str], overall: Overall
) -> None:
    result = assess(given)
    assert {p: start(result.levels, p) for p in expected_steps} == expected_steps
    assert result.overall == overall


def test_every_pattern_gets_a_level() -> None:
    assert set(assess(answers()).levels) == set(PatternCode)


def test_shift_moves_every_pattern_and_never_below_one() -> None:
    base = assess(answers()).levels
    lower = assess(answers(), shift=-1).levels
    higher = assess(answers(), shift=1).levels
    assert all(lower[p] == max(1, base[p] - 1) for p in base)
    assert all(higher[p] == base[p] + 1 for p in base)


@pytest.mark.parametrize(
    ("experienced", "knows_terms", "guidance"),
    [
        (False, False, "verbose"),
        (True, False, "verbose"),
        (False, True, "verbose"),
        (True, True, "normal"),
    ],
)
def test_guidance_level(experienced: bool, knows_terms: bool, guidance: str) -> None:
    result = assess(answers(experienced=experienced, knows_terms=knows_terms))
    assert result.guidance_level == guidance


def test_main_line_skips_variants() -> None:
    line = [e.slug for e in main_line(pattern_exercises("pull_v"))]
    assert line[:3] == ["band_pulldown", "australian_pullup_high", "australian_pullup_low"]
    assert "chin_up" not in line
    assert line[-1] == "muscle_up"
