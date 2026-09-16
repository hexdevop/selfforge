"""Reference data shared by all users (docs/02-data-model.md). Filled only by the
idempotent seed (`python -m app.seed`), never by migrations or the API."""

from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.engine.types import is_timed


class MovementPattern(TimestampMixin, Base):
    __tablename__ = "movement_patterns"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    title_ru: Mapped[str] = mapped_column(String(100))
    description_ru: Mapped[str] = mapped_column(Text)
    is_bilateral_default: Mapped[bool] = mapped_column(Boolean)


class EquipmentItem(TimestampMixin, Base):
    __tablename__ = "equipment_items"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    title_ru: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(32))
    supports_quantity: Mapped[bool] = mapped_column(Boolean)
    supports_weight_list: Mapped[bool] = mapped_column(Boolean)
    is_outdoor: Mapped[bool] = mapped_column(Boolean)


class Exercise(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercises"
    __table_args__ = (
        Index("ix_exercises_pattern_level", "pattern_code", "difficulty_level"),
        Index("ix_exercises_required_equipment", "required_equipment", postgresql_using="gin"),
    )

    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title_ru: Mapped[str] = mapped_column(String(150))
    pattern_code: Mapped[str] = mapped_column(ForeignKey("movement_patterns.code"))
    # Position on the pattern's single difficulty scale; variants share their step's level.
    difficulty_level: Mapped[int] = mapped_column(Integer)
    # Share of body mass lifted per rep; tonnage of bodyweight work (docs/03-engine.md §7).
    bodyweight_share: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), default=Decimal(0), server_default="0"
    )

    is_unilateral: Mapped[bool] = mapped_column(Boolean)
    requires_pair: Mapped[bool] = mapped_column(Boolean)
    is_quiet: Mapped[bool] = mapped_column(Boolean)
    needs_floor_space: Mapped[bool] = mapped_column(Boolean)
    needs_ceiling_height: Mapped[bool] = mapped_column(Boolean)
    lies_on_floor: Mapped[bool] = mapped_column(Boolean)

    # AND of OR-groups: [["pullup_bar", "rings"], ["backpack"]]; [] means bodyweight only.
    required_equipment: Mapped[list[list[str]]] = mapped_column(JSONB)
    primary_muscles: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    secondary_muscles: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    contraindicated_for: Mapped[list[str]] = mapped_column(ARRAY(String(32)))

    technique_ru: Mapped[str] = mapped_column(Text)
    common_mistakes_ru: Mapped[list[str]] = mapped_column(ARRAY(Text))
    media: Mapped[dict[str, Any]] = mapped_column(JSONB)

    # Plain slugs, not FKs: the seed validates the ladder as a whole.
    prev_slug: Mapped[str | None] = mapped_column(String(64))
    next_slug: Mapped[str | None] = mapped_column(String(64))
    progression_criteria: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    @property
    def timed(self) -> bool:
        """Measured in seconds of work rather than reps."""
        return is_timed(self.pattern_code, self.progression_criteria)


class Skill(TimestampMixin, Base):
    __tablename__ = "skills"

    slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    title_ru: Mapped[str] = mapped_column(String(150))
    description_ru: Mapped[str] = mapped_column(Text)
    # {"exercise_slug", "reps" | "hold_seconds"}: the result that counts as achieved;
    # null for a skill with no exercise of its own, marked by hand.
    goal: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    prerequisites: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    lead_up_exercise_slugs: Mapped[list[str]] = mapped_column(ARRAY(String(64)))
