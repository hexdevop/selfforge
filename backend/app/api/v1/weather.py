from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencies.auth import CurrentActiveUser
from app.dependencies.db import DbSession
from app.schemas.weather import ForecastQuery, ForecastRead
from app.services.weather import WeatherService

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/forecast", response_model=ForecastRead)
async def forecast(
    query: Annotated[ForecastQuery, Query()], user: CurrentActiveUser, session: DbSession
) -> ForecastRead:
    """The next hours at an outdoor place and whether to move today's workout indoors."""
    return await WeatherService(session, user).forecast(query.location_id)
