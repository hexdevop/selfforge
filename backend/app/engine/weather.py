"""Whether the forecast turns an outdoor workout into a home one (docs/01-domain.md, «Погода»)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

# Beyond these the same workout is offered at home.
RAIN_MM_PER_HOUR = 0.5
RAIN_PROBABILITY = 60
GUST_MS = 15.0
COLD_APPARENT_C = -15.0
HEAT_APPARENT_C = 32.0
# Softer: only advice on how to train outside.
FROST_APPARENT_C = 0.0
WARM_APPARENT_C = 27.0
# People open the day card when getting ready to go; the window covers the way and the work.
MIN_WINDOW_MINUTES = 180

# WMO weather codes for snow: snowfall, snow grains, snow showers.
_SNOW_CODES = frozenset({71, 73, 75, 77, 85, 86})


class Concern(StrEnum):
    RAIN = "rain"
    SNOW = "snow"
    WIND = "wind"
    COLD = "cold"
    HEAT = "heat"


class Hint(StrEnum):
    FROST = "frost"
    WARM = "warm"


@dataclass(frozen=True)
class HourForecast:
    at: datetime  # start of the hour, timezone-aware
    temperature_c: float
    apparent_c: float
    precipitation_mm: float
    precipitation_probability: int  # percent
    wind_gust_ms: float
    weather_code: int


@dataclass(frozen=True)
class Verdict:
    move_indoors: bool
    concerns: tuple[Concern, ...]
    hints: tuple[Hint, ...]
    window_start: datetime
    window_end: datetime
    min_apparent_c: float
    max_apparent_c: float
    max_gust_ms: float
    max_precipitation_mm: float
    max_precipitation_probability: int
    text_ru: str


def _degrees(value: float) -> str:
    rounded = round(value)
    sign = "+" if rounded > 0 else "−" if rounded < 0 else ""
    return f"{sign}{abs(rounded)} °C"


def _number(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def assess(hours: Sequence[HourForecast], start: datetime, minutes: int) -> Verdict | None:
    """The hours overlapping [start, start + max(minutes, 3 h)]; None when the forecast
    doesn't reach that far."""
    end = start + timedelta(minutes=max(minutes, MIN_WINDOW_MINUTES))
    window = [h for h in hours if h.at < end and h.at + timedelta(hours=1) > start]
    if not window:
        return None

    min_apparent = min(h.apparent_c for h in window)
    max_apparent = max(h.apparent_c for h in window)
    max_gust = max(h.wind_gust_ms for h in window)
    max_mm = max(h.precipitation_mm for h in window)
    max_probability = max(h.precipitation_probability for h in window)
    wet = [
        h
        for h in window
        if h.precipitation_mm >= RAIN_MM_PER_HOUR or h.precipitation_probability >= RAIN_PROBABILITY
    ]

    concerns: list[Concern] = []
    if wet:
        snow = sum(h.weather_code in _SNOW_CODES for h in wet) * 2 > len(wet)
        concerns.append(Concern.SNOW if snow else Concern.RAIN)
    if max_gust >= GUST_MS:
        concerns.append(Concern.WIND)
    if min_apparent <= COLD_APPARENT_C:
        concerns.append(Concern.COLD)
    if max_apparent >= HEAT_APPARENT_C:
        concerns.append(Concern.HEAT)

    hints: list[Hint] = []
    if Concern.COLD not in concerns and min_apparent < FROST_APPARENT_C:
        hints.append(Hint.FROST)
    if Concern.HEAT not in concerns and max_apparent >= WARM_APPARENT_C:
        hints.append(Hint.WARM)

    parts = [
        _concern_text(c, min_apparent, max_apparent, max_gust, max_mm, max_probability)
        for c in concerns
    ]
    if concerns:
        parts.append("Ту же тренировку можно сделать дома: те же движения, другие снаряды.")
    parts += [_hint_text(h) for h in hints]
    if not parts:
        parts.append(
            f"Погода для улицы подходящая: по ощущению {_degrees(min_apparent)}"
            + (f"…{_degrees(max_apparent)}" if round(max_apparent) != round(min_apparent) else "")
            + "."
        )

    return Verdict(
        move_indoors=bool(concerns),
        concerns=tuple(concerns),
        hints=tuple(hints),
        window_start=start,
        window_end=end,
        min_apparent_c=min_apparent,
        max_apparent_c=max_apparent,
        max_gust_ms=max_gust,
        max_precipitation_mm=max_mm,
        max_precipitation_probability=max_probability,
        text_ru=" ".join(parts),
    )


def _concern_text(
    concern: Concern,
    min_apparent: float,
    max_apparent: float,
    gust: float,
    mm: float,
    probability: int,
) -> str:
    if concern in (Concern.RAIN, Concern.SNOW):
        what = "Дождь" if concern is Concern.RAIN else "Снег"
        amount = f"до {_number(mm)} мм в час, " if mm > 0 else ""
        return (
            f"{what} в ближайшие часы ({amount}вероятность {probability}%): "
            "перекладины и брусья будут мокрыми и скользкими."
        )
    if concern is Concern.WIND:
        return f"Порывы ветра до {_number(gust)} м/с."
    if concern is Concern.COLD:
        return (
            f"По ощущению до {_degrees(min_apparent)}: между подходами мышцы быстро остывают, "
            "а голые перекладины прихватывают руки."
        )
    return f"По ощущению до {_degrees(max_apparent)}: тяжёлая работа на солнце в такую жару."


def _hint_text(hint: Hint) -> str:
    if hint is Hint.FROST:
        return (
            "На улице минус: разомнись дома до выхода, между подходами двигайся, "
            "а статику — планки и висы — сократи."
        )
    return "Тепло: лучше утром или вечером, когда не печёт, и возьми с собой воду."
