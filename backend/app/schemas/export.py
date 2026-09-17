from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.body import BodyMetricRead, PhotoRead
from app.schemas.location import LocationRead
from app.schemas.profile import PatternLevelRead, ProfileRead
from app.schemas.program import ProgramRead
from app.schemas.user import UserRead
from app.schemas.workout import PersonalRecordRead, WorkoutSessionRead


class SkillProgressExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill_slug: str
    status: str
    current_lead_up_slug: str | None
    achieved_at: datetime | None


class Export(BaseModel):
    """Everything the app keeps about one person, in one file (docs/00-product.md, principle 6)."""

    format_version: int = 1
    exported_at: datetime
    user: UserRead
    profile: ProfileRead
    pattern_levels: list[PatternLevelRead]
    locations: list[LocationRead]
    programs: list[ProgramRead]
    workouts: list[WorkoutSessionRead] = Field(description="Oldest first, with every logged set")
    personal_records: list[PersonalRecordRead]
    body_metrics: list[BodyMetricRead]
    photos: list[PhotoRead] = Field(
        description="The files themselves are behind `url`, a link that works for 15 minutes"
    )
    skill_progress: list[SkillProgressExport]
