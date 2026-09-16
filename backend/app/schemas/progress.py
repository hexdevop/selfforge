from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.engine.analytics import Period, ResultKind, SkillStatus
from app.schemas.catalog import PatternCode
from app.schemas.types import WeightKg


class _Model(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, json_schema_serialization_defaults_required=True
    )


class ResultRead(_Model):
    kind: ResultKind = Field(description="est_1rm is kilograms; reps and seconds are counts")
    value: Decimal


class NearRecordRead(_Model):
    exercise_slug: str
    record: ResultRead
    last: ResultRead
    text_ru: str


class WeekRead(_Model):
    starts_on: date
    workouts: int
    tonnage_kg: WeightKg


class Summary(_Model):
    week_streak: int = Field(description="Weeks in a row with a workout; this week may be empty")
    this_week: WeekRead
    last_workout_at: datetime | None
    near_records: list[NearRecordRead]
    imbalances: int = Field(description="One-sided exercises with a gap over 15%")


class PatternPoint(_Model):
    day: date
    session_id: str
    exercise_slug: str
    level: int = Field(description="Step on the pattern's difficulty scale")
    result: ResultRead | None = Field(description="null when no set could be compared")


class PatternProgress(_Model):
    pattern_code: PatternCode
    points: list[PatternPoint]


class ExercisePoint(_Model):
    day: date
    session_id: str
    best: ResultRead | None
    top_weight_kg: WeightKg | None
    working_sets: int
    tonnage_kg: WeightKg


class ExerciseProgress(_Model):
    exercise_slug: str
    points: list[ExercisePoint]


class TonnagePoint(_Model):
    starts_on: date
    tonnage_kg: WeightKg


class TonnageQuery(BaseModel):
    period: Period = Period.WEEK
    pattern: PatternCode | None = None


class ImbalanceRead(_Model):
    exercise_slug: str
    weaker_side: str
    left_avg: Decimal
    right_avg: Decimal
    gap: Decimal = Field(description="Share of the stronger side: 0.2 is 20%")
    advice_ru: str


class TargetRead(_Model):
    exercise_slug: str
    reps: int | None
    hold_seconds: int | None
    best: int | None = Field(description="Best single working set so far, reps or seconds")
    met: bool


class SkillProgressRead(_Model):
    skill_slug: str
    title_ru: str
    description_ru: str
    status: SkillStatus
    goal: TargetRead | None = Field(description="null: no exercise to check, marked by hand")
    prerequisites: list[TargetRead]
    lead_up_exercise_slugs: list[str]
    current_lead_up_slug: str
    achieved_at: datetime | None


class SkillMark(BaseModel):
    achieved: bool
