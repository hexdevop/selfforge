"""ORM models. Import every model here so Alembic autogenerate can see them."""

from app.models.body import BodyMetric, ProgressPhoto, SkillProgress
from app.models.catalog import EquipmentItem, Exercise, MovementPattern, Skill
from app.models.location import Location, LocationEquipment
from app.models.profile import PatternLevel, Profile
from app.models.program import PlannedSession, Program, ProgramWeek
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.workout import PersonalRecord, SetLog, WorkoutSession

__all__ = [
    "BodyMetric",
    "EquipmentItem",
    "Exercise",
    "Location",
    "LocationEquipment",
    "MovementPattern",
    "PatternLevel",
    "PersonalRecord",
    "PlannedSession",
    "Profile",
    "ProgressPhoto",
    "Program",
    "ProgramWeek",
    "RefreshToken",
    "SetLog",
    "Skill",
    "SkillProgress",
    "User",
    "WorkoutSession",
]
