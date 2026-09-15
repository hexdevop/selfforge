import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Program(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "programs"
    __table_args__ = (
        # At most one active program per person; the rest are completed or abandoned.
        Index(
            "uq_programs_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    goal_primary: Mapped[str] = mapped_column(String(32))
    structure: Mapped[str] = mapped_column(String(16))
    weeks_total: Mapped[int] = mapped_column(SmallInteger)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="active")
    # Profile, levels and inventory as they were: explains the program and allows a rebuild.
    generation_input: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rationale_ru: Mapped[str] = mapped_column(Text)

    weeks: Mapped[list["ProgramWeek"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="ProgramWeek.index"
    )


class ProgramWeek(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "program_weeks"
    __table_args__ = (UniqueConstraint("program_id", "index"),)

    program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True
    )
    index: Mapped[int] = mapped_column(SmallInteger)
    kind: Mapped[str] = mapped_column(String(16))
    volume_multiplier: Mapped[Decimal] = mapped_column(Numeric(3, 2))

    sessions: Mapped[list["PlannedSession"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="PlannedSession.day_index"
    )


class PlannedSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planned_sessions"
    __table_args__ = (UniqueConstraint("program_week_id", "day_index"),)

    program_week_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("program_weeks.id", ondelete="CASCADE"), index=True
    )
    day_index: Mapped[int] = mapped_column(SmallInteger)
    # Kept when the place is deleted later: the plan stays readable, a rebuild picks a new one.
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL")
    )
    title_ru: Mapped[str] = mapped_column(String(100))
    focus: Mapped[list[str]] = mapped_column(ARRAY(String(16)))
    estimated_minutes: Mapped[int] = mapped_column(SmallInteger)
    # [{"kind", "minutes", "exercises": [{"exercise_slug", "sets", "target_min", ...}]}]
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
