import uuid
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationFailedException
from app.engine.weather import assess
from app.models.location import Location
from app.models.user import User
from app.repositories.location import LocationRepository
from app.schemas.location import OUTDOOR_KINDS, LocationKind
from app.schemas.weather import ForecastRead, HourRead, VerdictRead
from app.services.profile import ProfileService
from app.weather import hourly_forecast

_SHOWN_HOURS = 12


class WeatherService:
    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def forecast(self, location_id: uuid.UUID) -> ForecastRead:
        places = LocationRepository(self.session)
        location = await places.get_for_user(location_id, self.user.id)
        if location is None:
            raise NotFoundException("Такого места нет")
        if LocationKind(location.kind) not in OUTDOOR_KINDS:
            raise ValidationFailedException("Прогноз нужен только для уличных мест")
        if location.geo_lat is None or location.geo_lon is None:
            raise ValidationFailedException(
                "Отметь, где эта площадка, — тогда покажем прогноз",
                {"location_id": "У места нет координат"},
            )

        now = datetime.now(UTC)
        hours = await hourly_forecast(location.geo_lat, location.geo_lon, now)
        profile = await ProfileService(self.session, self.user).get()
        # The way there and back plus the workout itself.
        minutes = (profile.session_minutes or 45) + 2 * (location.travel_minutes or 0)
        verdict = assess(hours, now, minutes)

        this_hour = now.replace(minute=0, second=0, microsecond=0)
        until = this_hour + timedelta(hours=_SHOWN_HOURS)
        upcoming = [h for h in hours if this_hour <= h.at < until]
        return ForecastRead(
            location_id=location.id,
            verdict=VerdictRead.model_validate(asdict(verdict)) if verdict else None,
            hours=[HourRead.model_validate(asdict(h)) for h in upcoming],
            indoor_location_id=_indoor(await places.list_for_user(self.user.id)),
        )


def _indoor(locations: Sequence[Location]) -> uuid.UUID | None:
    """The default place if it's indoors, else the first indoor one (listed default-first)."""
    return next((loc.id for loc in locations if LocationKind(loc.kind) not in OUTDOOR_KINDS), None)
