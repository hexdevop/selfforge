import uuid
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Location(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Equipment belongs to a place, not to the person: home, park, hotel."""

    __tablename__ = "locations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(100))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    travel_minutes: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    # {"quiet_mode", "low_ceiling", "limited_space", "surface"}
    constraints: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    geo_lat: Mapped[float | None] = mapped_column(Float, default=None)
    geo_lon: Mapped[float | None] = mapped_column(Float, default=None)

    equipment: Mapped[list["LocationEquipment"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="LocationEquipment.equipment_code"
    )


class LocationEquipment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "location_equipment"
    __table_args__ = (UniqueConstraint("location_id", "equipment_code"),)

    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), index=True
    )
    equipment_code: Mapped[str] = mapped_column(ForeignKey("equipment_items.code"))
    # 1 or 2 — one dumbbell vs a pair changes which exercises exist at all.
    quantity: Mapped[int] = mapped_column(SmallInteger, default=1)
    # {"type": "adjustable", "bar_kg", "plates"} | {"type": "fixed", "weights_kg"} | {"resistances"}
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
