from datetime import UTC, datetime, timedelta

import pytest

from app.engine.weather import Concern, Hint, HourForecast, assess

T0 = datetime(2026, 9, 16, 9, tzinfo=UTC)


def hour(
    offset: int,
    *,
    apparent: float = 15,
    mm: float = 0,
    probability: int = 0,
    gust: float = 5,
    code: int = 1,
) -> HourForecast:
    return HourForecast(
        at=T0 + timedelta(hours=offset),
        temperature_c=apparent,
        apparent_c=apparent,
        precipitation_mm=mm,
        precipitation_probability=probability,
        wind_gust_ms=gust,
        weather_code=code,
    )


def day(**bad_hour: float) -> list[HourForecast]:
    """Twelve calm hours; hour 1 gets whatever is passed."""
    return [hour(i, **bad_hour) if i == 1 else hour(i) for i in range(12)]  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("hours", "concerns", "move"),
    [
        (day(), (), False),
        (day(mm=0.4, probability=50), (), False),  # a drizzle under both thresholds
        (day(mm=0.5, code=61), (Concern.RAIN,), True),
        (day(probability=60, code=80), (Concern.RAIN,), True),
        (day(mm=1.2, code=73), (Concern.SNOW,), True),
        (day(gust=14.9), (), False),
        (day(gust=15), (Concern.WIND,), True),
        (day(apparent=-14), (), False),
        (day(apparent=-15), (Concern.COLD,), True),
        (day(apparent=31), (), False),
        (day(apparent=32), (Concern.HEAT,), True),
    ],
    ids=[
        "calm",
        "drizzle",
        "rain mm",
        "rain chance",
        "snow",
        "gusty",
        "windy",
        "chilly",
        "cold",
        "hot",
        "too hot",
    ],
)
def test_thresholds(hours: list[HourForecast], concerns: tuple[Concern, ...], move: bool) -> None:
    verdict = assess(hours, T0, 60)
    assert verdict is not None
    assert (verdict.concerns, verdict.move_indoors) == (concerns, move)


def test_the_window_is_at_least_three_hours_and_ignores_what_comes_after() -> None:
    rain_at_four = [hour(i, mm=3, code=63) if i == 4 else hour(i) for i in range(12)]
    assert assess(rain_at_four, T0, 60).move_indoors is False  # type: ignore[union-attr]
    assert assess(rain_at_four, T0, 300).move_indoors is True  # type: ignore[union-attr]
    # Rain earlier this morning doesn't matter.
    assert assess(rain_at_four, T0 + timedelta(hours=5), 60).move_indoors is False  # type: ignore[union-attr]


def test_an_hour_already_started_is_in_the_window() -> None:
    raining_now = [hour(0, mm=2, code=63), *(hour(i) for i in range(1, 12))]
    verdict = assess(raining_now, T0 + timedelta(minutes=40), 60)
    assert verdict is not None and verdict.move_indoors


def test_no_forecast_for_the_window_is_no_verdict() -> None:
    assert assess([hour(0)], T0 + timedelta(hours=5), 60) is None


@pytest.mark.parametrize(
    ("apparent", "hints"),
    [(-3, (Hint.FROST,)), (-20, ()), (28, (Hint.WARM,)), (35, ()), (15, ())],
)
def test_soft_hints_only_where_the_workout_stays_outside(
    apparent: float, hints: tuple[Hint, ...]
) -> None:
    verdict = assess(day(apparent=apparent), T0, 60)
    assert verdict is not None and verdict.hints == hints


def test_texts_explain_and_offer_rather_than_forbid() -> None:
    rain = assess(day(mm=1.2, probability=80, code=61), T0, 60)
    assert rain is not None
    assert "Дождь в ближайшие часы (до 1,2 мм в час, вероятность 80%)" in rain.text_ru
    assert "можно сделать дома" in rain.text_ru

    cold = assess(day(apparent=-18), T0, 60)
    assert cold is not None and "−18 °C" in cold.text_ru

    frost = assess(day(apparent=-3), T0, 60)
    assert frost is not None and "разомнись дома до выхода" in frost.text_ru

    calm = assess(day(), T0, 60)
    assert calm is not None and calm.text_ru.startswith("Погода для улицы подходящая")
