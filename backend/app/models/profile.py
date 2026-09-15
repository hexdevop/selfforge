import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    sex: Mapped[str | None] = mapped_column(String(16), default=None)
    birth_year: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    height_cm: Mapped[int | None] = mapped_column(SmallInteger, default=None)

    goal_primary: Mapped[str | None] = mapped_column(String(32), default=None)
    goal_secondary: Mapped[str | None] = mapped_column(String(32), default=None)
    days_per_week: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    session_minutes: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    guidance_level: Mapped[str] = mapped_column(String(16), default="normal")

    health_flags: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    # Only the conclusion of the start-up screen is stored, not which condition it was.
    needs_medical_clearance: Mapped[bool] = mapped_column(Boolean, default=False)
    medical_disclaimer_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    units: Mapped[str] = mapped_column(String(16), default="metric")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )


class PatternLevel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The user's step on each pattern's ladder — kept per pattern, not as one number."""

    __tablename__ = "pattern_levels"
    __table_args__ = (UniqueConstraint("user_id", "pattern_code"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    pattern_code: Mapped[str] = mapped_column(ForeignKey("movement_patterns.code"))
    current_exercise_slug: Mapped[str] = mapped_column(ForeignKey("exercises.slug"))
    estimated_level: Mapped[int] = mapped_column(Integer)
    assessment_source: Mapped[str] = mapped_column(String(16))
