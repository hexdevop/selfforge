import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BodyMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One measuring moment; every value is optional — people weigh daily, tape monthly."""

    __tablename__ = "body_metrics"
    __table_args__ = (Index("ix_body_metrics_user_measured", "user_id", "measured_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
    waist_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), default=None)
    chest_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), default=None)
    hip_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), default=None)
    arm_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), default=None)
    thigh_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), default=None)
    note: Mapped[str | None] = mapped_column(Text, default=None)


class ProgressPhoto(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Private by default. The file lives in object storage; only its key is kept here."""

    __tablename__ = "progress_photos"
    __table_args__ = (Index("ix_progress_photos_user_taken", "user_id", "taken_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    angle: Mapped[str] = mapped_column(String(8))


class SkillProgress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skill_progress"
    __table_args__ = (UniqueConstraint("user_id", "skill_slug"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    skill_slug: Mapped[str] = mapped_column(ForeignKey("skills.slug"))
    status: Mapped[str] = mapped_column(String(16), default="locked")
    current_lead_up_slug: Mapped[str | None] = mapped_column(String(64), default=None)
    # Set once: a skill once achieved stays achieved, a weak week doesn't take it away.
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
