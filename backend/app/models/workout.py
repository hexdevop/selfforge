import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkoutSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workout_sessions"
    __table_args__ = (
        Index("ix_workout_sessions_user_started", "user_id", "started_at"),
        # Only one workout can be running at a time; starting another closes the previous.
        Index(
            "uq_workout_sessions_one_in_progress_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Null for an unplanned workout; kept when the plan is deleted so history stays readable.
    planned_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("planned_sessions.id", ondelete="SET NULL"), default=None
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), default=None
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    status: Mapped[str] = mapped_column(String(16), default="in_progress")
    # {"sleep", "stress", "soreness"} — the three taps before the start.
    readiness: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # The session as prepared: blocks with concrete weights, reshaped by swaps and trimming.
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # [{"from", "to", "reason", "at"}] — repeated refusals are a signal for the next rebuild.
    substitutions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    total_tonnage_kg: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal(0))
    note: Mapped[str | None] = mapped_column(Text, default=None)

    sets: Mapped[list["SetLog"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="SetLog.performed_at"
    )


class SetLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The history table. Grows faster than anything else here."""

    __tablename__ = "set_logs"
    __table_args__ = (
        # The client buffers sets and resends them with retries: the same set must land once.
        UniqueConstraint("client_uuid", name="uq_set_logs_client_uuid"),
        Index("ix_set_logs_user_performed", "user_id", "performed_at"),
        Index("ix_set_logs_user_exercise_performed", "user_id", "exercise_slug", "performed_at"),
    )

    client_uuid: Mapped[uuid.UUID] = mapped_column()
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True
    )
    # Denormalised from the session so the history queries never join.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    exercise_slug: Mapped[str] = mapped_column(ForeignKey("exercises.slug"))
    pattern_code: Mapped[str] = mapped_column(ForeignKey("movement_patterns.code"))
    set_index: Mapped[int] = mapped_column(SmallInteger)
    side: Mapped[str] = mapped_column(String(8), default="both")
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), default=None)
    added_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), default=None)
    band: Mapped[str | None] = mapped_column(String(32), default=None)
    reps: Mapped[int] = mapped_column(SmallInteger)
    tempo: Mapped[str | None] = mapped_column(String(16), default=None)
    rir: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    # Words instead of a number for people who can't rate reps in reserve yet.
    effort_label: Mapped[str | None] = mapped_column(String(16), default=None)
    is_warmup: Mapped[bool] = mapped_column(Boolean, default=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PersonalRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "personal_records"
    __table_args__ = (UniqueConstraint("user_id", "exercise_slug", "kind"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    exercise_slug: Mapped[str] = mapped_column(ForeignKey("exercises.slug"))
    pattern_code: Mapped[str] = mapped_column(ForeignKey("movement_patterns.code"))
    kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    achieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    set_log_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("set_logs.id", ondelete="SET NULL"), default=None
    )
