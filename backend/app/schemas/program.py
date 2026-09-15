import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.engine.goals import Goal
from app.engine.mesocycle import BlockKind, Structure, WeekKind
from app.schemas.catalog import PatternCode


class ProgramStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class _Model(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, json_schema_serialization_defaults_required=True
    )


class PlannedExerciseRead(_Model):
    exercise_slug: str
    pattern_code: PatternCode
    sets: int
    target_min: int
    target_max: int
    timed: bool = Field(description="target is seconds of work, not reps")
    rest_seconds: int
    rir: int = Field(description="reps in reserve: stop the set this far from failure")
    tempo: str | None = Field(default=None, description="eccentric-pause-concentric, seconds")


class BlockRead(_Model):
    kind: BlockKind
    minutes: int
    exercises: list[PlannedExerciseRead] = []


class PlannedSessionRead(_Model):
    id: uuid.UUID | None = Field(default=None, description="null in a preview")
    day_index: int
    location_id: uuid.UUID | None
    title_ru: str
    focus: list[PatternCode]
    estimated_minutes: int
    blocks: list[BlockRead]


class ProgramWeekRead(_Model):
    index: int
    kind: WeekKind
    volume_multiplier: float
    sessions: list[PlannedSessionRead]


class ProgramDraft(_Model):
    goal_primary: Goal
    structure: Structure
    weeks_total: int
    rationale_ru: str
    weeks: list[ProgramWeekRead]


class ProgramRead(ProgramDraft):
    id: uuid.UUID
    status: ProgramStatus
    started_at: datetime


class ProgramRequest(BaseModel):
    day_locations: list[uuid.UUID] | None = Field(
        default=None,
        description="Location for each training day, in order; all days at the default one "
        "if omitted",
    )
