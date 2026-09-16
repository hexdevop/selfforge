"""The forecast provider, behind a Redis cache. Only the backend talks to it.

Cached by coordinates rounded to ~1 km and the hour: everyone training in one district
within the same hour shares one request, and a forecast doesn't change faster than that.
"""

import json
from datetime import UTC, datetime
from typing import Any

import httpx

from app.cache import redis as cache
from app.core.config import settings
from app.core.exceptions import ServiceUnavailableException
from app.engine.weather import HourForecast

_HOURLY = (
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "precipitation_probability",
    "wind_gusts_10m",
    "weather_code",
)


async def _fetch(lat: float, lon: float) -> dict[str, Any]:
    params: dict[str, str | float | int] = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(_HOURLY),
        "wind_speed_unit": "ms",
        "timezone": "UTC",
        "forecast_days": 2,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.WEATHER_TIMEOUT_SECONDS) as client:
            response = await client.get(settings.WEATHER_API_URL, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data
    except (httpx.HTTPError, ValueError) as exc:
        raise ServiceUnavailableException(
            "Прогноз сейчас недоступен — проверь погоду в окно и загляни позже"
        ) from exc


def _parse(data: dict[str, Any]) -> list[HourForecast]:
    hourly = data["hourly"]

    def value(name: str, i: int) -> float:
        raw = hourly[name][i]
        return float(raw) if raw is not None else 0.0

    return [
        HourForecast(
            at=datetime.fromisoformat(at).replace(tzinfo=UTC),
            temperature_c=value("temperature_2m", i),
            apparent_c=value("apparent_temperature", i),
            precipitation_mm=value("precipitation", i),
            precipitation_probability=int(value("precipitation_probability", i)),
            wind_gust_ms=value("wind_gusts_10m", i),
            weather_code=int(value("weather_code", i)),
        )
        for i, at in enumerate(hourly["time"])
    ]


async def hourly_forecast(lat: float, lon: float, now: datetime) -> list[HourForecast]:
    key = f"weather:{lat:.2f}:{lon:.2f}:{now.astimezone(UTC):%Y%m%d%H}"
    stored = await cache.redis_client.get(key)
    if stored is not None:
        return _parse(json.loads(stored))
    data = await _fetch(round(lat, 2), round(lon, 2))
    try:
        hours = _parse(data)  # parse before caching: a malformed answer isn't worth keeping
    except (KeyError, TypeError, ValueError) as exc:
        raise ServiceUnavailableException(
            "Прогноз пришёл в непонятном виде — загляни позже"
        ) from exc
    await cache.redis_client.set(key, json.dumps(data), ex=settings.WEATHER_CACHE_SECONDS)
    return hours
