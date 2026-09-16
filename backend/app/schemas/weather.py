import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.engine.weather import Concern, Hint


class _Model(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, json_schema_serialization_defaults_required=True
    )


class HourRead(_Model):
    at: datetime
    temperature_c: float
    apparent_c: float
    precipitation_mm: float
    precipitation_probability: int
    wind_gust_ms: float
    weather_code: int = Field(description="WMO code")


class VerdictRead(_Model):
    move_indoors: bool = Field(description="Offer the same workout at home")
    concerns: list[Concern]
    hints: list[Hint] = Field(description="Advice for training outside anyway")
    window_start: datetime
    window_end: datetime
    min_apparent_c: float
    max_apparent_c: float
    max_gust_ms: float
    max_precipitation_mm: float
    max_precipitation_probability: int
    text_ru: str


class ForecastRead(_Model):
    location_id: uuid.UUID
    verdict: VerdictRead | None = Field(description="null when the forecast doesn't reach")
    hours: list[HourRead] = Field(description="The next twelve hours")
    indoor_location_id: uuid.UUID | None = Field(
        description="Where to move the workout: the default indoor place, if there is one"
    )


class ForecastQuery(BaseModel):
    location_id: uuid.UUID


class SwapLocationRequest(BaseModel):
    location_id: uuid.UUID
