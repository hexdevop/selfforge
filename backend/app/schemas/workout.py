import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.engine.mesocycle import BlockKind
from app.engine.session import Feeling, SubstitutionReason
from app.schemas.catalog import PatternCode
from app.schemas.types import WeightKg


class SessionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"


class Side(StrEnum):
    BOTH = "both"
    LEFT = "left"
    RIGHT = "right"


class RecordKind(StrEnum):
    MAX_WEIGHT = "max_weight"
    MAX_REPS = "max_reps"
    EST_1RM = "est_1rm"
    MAX_VOLUME = "max_volume"


class EffortLabel(StrEnum):
    """Words instead of reps in reserve, for people who can't rate that yet."""

    EASY = "easy"
    SOLID = "solid"
    HARD = "hard"
    LIMIT = "limit"


class _Model(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, json_schema_serialization_defaults_required=True
    )


class Readiness(_Model):
    """Three taps before the start; `good` means slept well, calm, not sore."""

    sleep: Feeling = Feeling.OK
    stress: Feeling = Feeling.OK
    soreness: Feeling = Feeling.OK


class DrillRead(_Model):
    title_ru: str
    seconds: int


class SessionExerciseRead(_Model):
    exercise_slug: str
    pattern_code: PatternCode
    sets: int
    target_min: int
    target_max: int
    timed: bool = Field(description="target is seconds of work, not reps")
    rest_seconds: int
    rir: int
    unilateral: bool = Field(description="log each side separately; both sides do equal reps")
    weight_kg: WeightKg | None = None
    tempo: str | None = None
    hint_ru: str = ""
    planned_slug: str = Field(default="", description="the plan slot this fills; a swap keeps it")


class SessionBlockRead(_Model):
    kind: BlockKind
    minutes: int
    exercises: list[SessionExerciseRead] = []
    drills: list[DrillRead] = []


class SubstitutionRead(_Model):
    from_slug: str
    to_slug: str
    reason: SubstitutionReason
    at: datetime


class SetLogIn(BaseModel):
    """One confirmed set. `client_uuid` makes resending the whole buffer harmless."""

    client_uuid: uuid.UUID
    exercise_slug: str
    set_index: int = Field(ge=0, le=50)
    reps: int = Field(ge=0, le=500)
    performed_at: datetime
    side: Side = Side.BOTH
    weight_kg: WeightKg | None = Field(default=None, ge=0, le=500)
    added_weight_kg: WeightKg | None = Field(default=None, ge=0, le=200)
    band: str | None = Field(default=None, max_length=32)
    tempo: str | None = Field(default=None, max_length=16)
    rir: int | None = Field(default=None, ge=0, le=10)
    effort_label: EffortLabel | None = None
    is_warmup: bool = False


class SetLogRead(_Model):
    id: uuid.UUID
    client_uuid: uuid.UUID
    exercise_slug: str
    pattern_code: PatternCode
    set_index: int
    side: Side
    reps: int
    weight_kg: WeightKg | None
    added_weight_kg: WeightKg | None
    band: str | None
    tempo: str | None
    rir: int | None
    effort_label: EffortLabel | None
    is_warmup: bool
    performed_at: datetime


class PersonalRecordRead(_Model):
    exercise_slug: str
    pattern_code: PatternCode
    kind: RecordKind
    value: Decimal
    achieved_at: datetime


class WorkoutSessionRead(_Model):
    id: uuid.UUID
    planned_session_id: uuid.UUID | None
    location_id: uuid.UUID | None
    status: SessionStatus
    started_at: datetime
    finished_at: datetime | None
    readiness: Readiness
    blocks: list[SessionBlockRead]
    notes_ru: list[str]
    substitutions: list[SubstitutionRead]
    total_tonnage_kg: WeightKg
    note: str | None
    sets: list[SetLogRead]


class SessionStart(BaseModel):
    planned_session_id: uuid.UUID | None = Field(
        default=None, description="Omit for an unplanned workout at the given place"
    )
    location_id: uuid.UUID | None = Field(
        default=None, description="Defaults to the place the plan names, then the default one"
    )
    readiness: Readiness = Readiness()


class SetsBatch(BaseModel):
    sets: list[SetLogIn] = Field(min_length=1, max_length=200)


class SetsAccepted(_Model):
    accepted: list[uuid.UUID] = Field(description="client_uuid of every set now stored")
    records: list[PersonalRecordRead] = Field(default=[], description="beaten by this batch")
    total_tonnage_kg: WeightKg


class SubstituteRequest(BaseModel):
    exercise_slug: str
    reason: SubstitutionReason


class TrimRequest(BaseModel):
    minutes_left: int = Field(ge=1, le=240)


class SessionFinish(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
