from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PatternCode(StrEnum):
    SQUAT = "squat"
    HINGE = "hinge"
    PUSH_H = "push_h"
    PUSH_V = "push_v"
    PULL_H = "pull_h"
    PULL_V = "pull_v"
    LUNGE = "lunge"
    CARRY = "carry"
    CORE = "core"
    CARDIO = "cardio"


class Muscle(StrEnum):
    CHEST = "chest"
    FRONT_DELTS = "front_delts"
    SIDE_DELTS = "side_delts"
    REAR_DELTS = "rear_delts"
    TRICEPS = "triceps"
    BICEPS = "biceps"
    FOREARMS = "forearms"
    LATS = "lats"
    UPPER_BACK = "upper_back"
    LOWER_BACK = "lower_back"
    ABS = "abs"
    OBLIQUES = "obliques"
    GLUTES = "glutes"
    QUADS = "quads"
    HAMSTRINGS = "hamstrings"
    ADDUCTORS = "adductors"
    CALVES = "calves"
    HIP_FLEXORS = "hip_flexors"


class HealthTag(StrEnum):
    KNEES = "knees"
    SHOULDERS = "shoulders"
    LOWER_BACK = "lower_back"
    WRISTS = "wrists"
    NECK = "neck"
    ELBOWS = "elbows"


class EquipmentCategory(StrEnum):
    WEIGHTS = "weights"
    BARS = "bars"
    BANDS = "bands"
    BENCH = "bench"
    SUPPORT = "support"
    BODYWEIGHT = "bodyweight"


class ProgressionCriteria(BaseModel):
    """What to complete before moving to the next step, e.g. 3×12 or 3×30 s."""

    sets: int = Field(ge=1)
    reps: int | None = Field(default=None, ge=1)
    hold_seconds: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _reps_or_hold(self) -> Self:
        if (self.reps is None) == (self.hold_seconds is None):
            raise ValueError("exactly one of reps / hold_seconds is required")
        return self


class SkillPrerequisite(BaseModel):
    exercise_slug: str
    reps: int | None = Field(default=None, ge=1)
    hold_seconds: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _reps_or_hold(self) -> Self:
        if (self.reps is None) == (self.hold_seconds is None):
            raise ValueError("exactly one of reps / hold_seconds is required")
        return self


class PatternRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: PatternCode
    title_ru: str
    description_ru: str
    is_bilateral_default: bool


class EquipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    title_ru: str
    category: EquipmentCategory
    supports_quantity: bool
    supports_weight_list: bool
    is_outdoor: bool


class ExerciseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title_ru: str
    pattern_code: PatternCode
    difficulty_level: int
    is_unilateral: bool
    requires_pair: bool
    is_quiet: bool
    timed: bool = Field(description="reps are seconds of work: planks, carries, holds")
    required_equipment: list[list[str]] = Field(
        description="AND of OR-groups of equipment codes; empty means bodyweight only"
    )
    primary_muscles: list[Muscle]


class ExerciseRead(ExerciseSummary):
    needs_floor_space: bool
    needs_ceiling_height: bool
    lies_on_floor: bool
    secondary_muscles: list[Muscle]
    contraindicated_for: list[HealthTag]
    technique_ru: str
    common_mistakes_ru: list[str]
    media: dict[str, str]
    prev_slug: str | None
    next_slug: str | None
    progression_criteria: ProgressionCriteria | None


class LadderRead(BaseModel):
    pattern: PatternRead
    exercises: list[ExerciseSummary] = Field(description="Ordered by difficulty_level")


class SkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title_ru: str
    description_ru: str
    prerequisites: list[SkillPrerequisite]
    lead_up_exercise_slugs: list[str]
