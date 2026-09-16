import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator

from app.schemas.types import WeightKg

Cm = Annotated[
    Decimal,
    Field(gt=0, le=300, decimal_places=1),
    PlainSerializer(lambda cm: f"{cm:.1f}", return_type=str),
]
BodyKg = Annotated[WeightKg, Field(gt=20, le=400, decimal_places=2)]

_MEASURES = ("weight_kg", "waist_cm", "chest_cm", "hip_cm", "arm_cm", "thigh_cm")


class PhotoAngle(StrEnum):
    FRONT = "front"
    SIDE = "side"
    BACK = "back"


class _Model(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, json_schema_serialization_defaults_required=True
    )


class BodyMetricIn(BaseModel):
    measured_at: datetime | None = Field(default=None, description="Now if omitted")
    weight_kg: BodyKg | None = None
    waist_cm: Cm | None = None
    chest_cm: Cm | None = None
    hip_cm: Cm | None = None
    arm_cm: Cm | None = None
    thigh_cm: Cm | None = None
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _something_measured(self) -> Self:
        if all(getattr(self, name) is None for name in _MEASURES):
            raise ValueError("Укажи хотя бы одно значение")
        return self


class BodyMetricRead(_Model):
    id: uuid.UUID
    measured_at: datetime
    weight_kg: WeightKg | None
    waist_cm: Cm | None
    chest_cm: Cm | None
    hip_cm: Cm | None
    arm_cm: Cm | None
    thigh_cm: Cm | None
    note: str | None


class TrendPoint(_Model):
    day: date
    weight_kg: WeightKg


class BodyMetrics(_Model):
    items: list[BodyMetricRead] = Field(description="Raw measurements, newest first")
    weight_trend: list[TrendPoint] = Field(
        description="7-day moving average — the weight line to show, not the raw values"
    )


class PhotoUploadRequest(BaseModel):
    angle: PhotoAngle
    taken_at: datetime | None = Field(default=None, description="Now if omitted")
    content_type: str = Field(pattern=r"^image/(jpeg|png|webp|heic|heif)$")


class PhotoRead(_Model):
    id: uuid.UUID
    taken_at: datetime
    angle: PhotoAngle
    url: str = Field(description="Short-lived link to view the photo")


class UploadForm(_Model):
    url: str
    fields: dict[str, Any] = Field(description="Send as multipart form fields, file last")


class PhotoUpload(_Model):
    photo: PhotoRead
    upload: UploadForm
