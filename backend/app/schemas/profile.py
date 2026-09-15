from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.engine.assessment import Overall, Pistol, Pullups, Pushups, Squats
from app.engine.goals import Goal
from app.schemas.catalog import HealthTag, PatternCode


class GuidanceLevel(StrEnum):
    VERBOSE = "verbose"
    NORMAL = "normal"
    QUIET = "quiet"


class AssessmentSource(StrEnum):
    ONBOARDING = "onboarding"
    PERFORMANCE = "performance"
    MANUAL = "manual"


BirthYear = Annotated[int, Field(ge=1920, le=datetime.now(UTC).year - 14)]


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    birth_year: int | None
    goal_primary: Goal | None
    goal_secondary: Goal | None
    days_per_week: int | None
    session_minutes: int | None
    guidance_level: GuidanceLevel
    health_flags: list[HealthTag]
    needs_medical_clearance: bool
    medical_disclaimer_accepted_at: datetime | None
    units: Literal["metric", "imperial"]
    timezone: str
    onboarding_completed_at: datetime | None


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    birth_year: BirthYear | None = None
    goal_primary: Goal | None = None
    goal_secondary: Goal | None = None
    days_per_week: int | None = Field(default=None, ge=2, le=6)
    session_minutes: int | None = Field(default=None, ge=15, le=120)
    guidance_level: GuidanceLevel | None = None
    health_flags: list[HealthTag] | None = None
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str | None) -> str | None:
        if value is not None and value not in available_timezones():
            raise ValueError("Неизвестный часовой пояс")
        return value

    @model_validator(mode="after")
    def _distinct_goals(self) -> Self:
        if self.goal_secondary is not None and self.goal_secondary == self.goal_primary:
            raise ValueError("Второстепенная цель должна отличаться от основной")
        return self


class DisclaimerRequest(BaseModel):
    """Start-up health screen. The answers only decide the recommendation; they aren't stored."""

    birth_year: BirthYear
    heart_condition: bool
    pregnancy: bool
    recent_injury: bool
    health_flags: list[HealthTag] = []
    accepted: Literal[True]


class AssessmentRequest(BaseModel):
    pushups: Pushups
    pullups: Pullups
    squats: Squats
    pistol: Pistol
    experienced: bool
    knows_terms: bool
    shift: Literal[-1, 0, 1] = 0


class PatternLevelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pattern_code: PatternCode
    estimated_level: int
    current_exercise_slug: str
    assessment_source: AssessmentSource


class AssessmentRead(BaseModel):
    overall: Overall
    guidance_level: GuidanceLevel
    levels: list[PatternLevelRead]


class PatternLevelUpdate(BaseModel):
    pattern_code: PatternCode
    estimated_level: int = Field(ge=1, le=20)
