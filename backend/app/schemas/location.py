import uuid
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.engine.types import Surface
from app.schemas.types import PositiveKg as Kg
from app.schemas.types import WeightKg


class LocationKind(StrEnum):
    HOME = "home"
    OUTDOOR_GYM = "outdoor_gym"
    OUTDOOR_BARE = "outdoor_bare"
    TRAVEL = "travel"


class BandResistance(StrEnum):
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


class _Model(BaseModel):
    # Fields with defaults are always present in responses; say so in the OpenAPI schema
    # so generated TS types don't mark them optional.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Constraints(_Model):
    quiet_mode: bool = False
    low_ceiling: bool = False
    limited_space: bool = False
    surface: Surface | None = None


class PlateSet(BaseModel):
    kg: Kg
    count: int = Field(ge=1, le=50)


class EquipmentDetails(_Model):
    """`fixed`: weights_kg, one entry per piece (two 16 kg bells → [16, 16]).
    `adjustable`: bar_kg + plates. Bands: resistances. Everything else: empty."""

    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    type: Literal["fixed", "adjustable"] | None = None
    weights_kg: list[Kg] = Field(default=[], max_length=30)
    bar_kg: Kg | None = None
    plates: list[PlateSet] = Field(default=[], max_length=15)
    resistances: list[BandResistance] = []


class LocationEquipmentIn(_Model):
    equipment_code: str
    quantity: int = Field(default=1, ge=1, le=2)
    details: EquipmentDetails = EquipmentDetails()


class LocationEquipmentRead(LocationEquipmentIn):
    model_config = ConfigDict(
        from_attributes=True, json_schema_serialization_defaults_required=True
    )


OUTDOOR_KINDS = frozenset({LocationKind.OUTDOOR_GYM, LocationKind.OUTDOOR_BARE})


def _coarse(value: float | None) -> float | None:
    """Two decimals is about a kilometre: plenty for a forecast, too coarse to be an address."""
    return None if value is None else round(value, 2)


Latitude = Annotated[float | None, Field(ge=-90, le=90), AfterValidator(_coarse)]
Longitude = Annotated[float | None, Field(ge=-180, le=180), AfterValidator(_coarse)]


class LocationCreate(BaseModel):
    kind: LocationKind
    title: str = Field(min_length=1, max_length=100)
    is_default: bool = False
    travel_minutes: int | None = Field(default=None, ge=0, le=180)
    constraints: Constraints = Constraints()
    geo_lat: Latitude = Field(default=None, description="Outdoor places only; stored at ~1 km")
    geo_lon: Longitude = None


class LocationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=100)
    is_default: bool | None = None
    travel_minutes: int | None = Field(default=None, ge=0, le=180)
    constraints: Constraints | None = None
    geo_lat: Latitude = None
    geo_lon: Longitude = None


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: LocationKind
    title: str
    is_default: bool
    travel_minutes: int | None
    constraints: Constraints
    geo_lat: float | None
    geo_lon: float | None
    equipment: list[LocationEquipmentRead]
    available_exercise_count: int = Field(
        description="Exercises doable here, given the equipment, constraints and health flags"
    )


class WeightGrid(BaseModel):
    equipment_code: str
    weights_kg: list[WeightKg]
    min_step_kg: WeightKg | None


class PlatesRequest(BaseModel):
    equipment_code: Literal["barbell", "dumbbell"]
    target_kg: Kg


class PlatesRead(BaseModel):
    target_kg: WeightKg
    achievable: bool
    per_side: list[PlateSet] = Field(description="Plates for EACH side, heaviest first")
    nearest_kg: list[WeightKg] = Field(description="Closest reachable weights when not achievable")
