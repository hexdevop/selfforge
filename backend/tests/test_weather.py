from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.exceptions import ServiceUnavailableException
from tests.conftest import signed_in
from tests.test_sessions import a_set, exercises, start, with_program

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("catalog")]


def open_meteo(rain_mm: float = 0.0, gust: float = 4.0) -> dict[str, Any]:
    """An Open-Meteo answer for 48 hours from the start of the current hour."""
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    times = [start + timedelta(hours=i) for i in range(48)]
    return {
        "hourly": {
            "time": [t.strftime("%Y-%m-%dT%H:%M") for t in times],
            "temperature_2m": [14.0] * 48,
            "apparent_temperature": [13.0] * 48,
            "precipitation": [rain_mm] * 48,
            "precipitation_probability": [90 if rain_mm else 5] * 48,
            "wind_gusts_10m": [gust] * 48,
            "weather_code": [63 if rain_mm else 1] * 48,
        }
    }


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"answer": open_meteo(), "calls": [], "down": False}

    async def fetch(lat: float, lon: float) -> dict[str, Any]:
        state["calls"].append((lat, lon))
        if state["down"]:
            raise ServiceUnavailableException("Прогноз сейчас недоступен")
        return state["answer"]  # type: ignore[no-any-return]

    monkeypatch.setattr("app.weather._fetch", fetch)
    return state


async def places(client: AsyncClient) -> tuple[str, str, dict[str, Any]]:
    program = await with_program(client)
    locations = (await client.get("/api/v1/locations")).json()
    home = next(loc["id"] for loc in locations if loc["kind"] == "home")
    park = next(loc["id"] for loc in locations if loc["kind"] == "outdoor_gym")
    return home, park, program


async def pin(client: AsyncClient, location_id: str) -> None:
    response = await client.patch(
        f"/api/v1/locations/{location_id}", json={"geo_lat": 55.751244, "geo_lon": 37.618423}
    )
    assert response.status_code == 200, response.text


# --- coordinates ----------------------------------------------------------------------


async def test_coordinates_are_kept_only_to_a_kilometre(user_client: AsyncClient) -> None:
    _, park, _ = await places(user_client)
    await pin(user_client, park)
    stored = next(
        loc for loc in (await user_client.get("/api/v1/locations")).json() if loc["id"] == park
    )
    assert (stored["geo_lat"], stored["geo_lon"]) == (55.75, 37.62)


async def test_coordinates_belong_to_outdoor_places_and_come_in_pairs(
    user_client: AsyncClient,
) -> None:
    home, park, _ = await places(user_client)

    indoor = await user_client.patch(
        f"/api/v1/locations/{home}", json={"geo_lat": 55.7, "geo_lon": 37.6}
    )
    half = await user_client.patch(f"/api/v1/locations/{park}", json={"geo_lat": 55.7})

    assert indoor.status_code == 422 and "уличным" in indoor.json()["detail"]["fields"]["geo_lat"]
    assert half.status_code == 422 and "обе" in half.json()["detail"]["fields"]["geo_lat"]


# --- forecast -------------------------------------------------------------------------


async def test_rain_offers_the_workout_at_home(
    user_client: AsyncClient, provider: dict[str, Any]
) -> None:
    home, park, _ = await places(user_client)
    await pin(user_client, park)
    provider["answer"] = open_meteo(rain_mm=1.5)

    forecast = (
        await user_client.get("/api/v1/weather/forecast", params={"location_id": park})
    ).json()

    assert forecast["verdict"]["move_indoors"] is True
    assert forecast["verdict"]["concerns"] == ["rain"]
    assert "дома" in forecast["verdict"]["text_ru"]
    assert forecast["indoor_location_id"] == home
    assert len(forecast["hours"]) == 12


async def test_fine_weather_stays_outside(
    user_client: AsyncClient, provider: dict[str, Any]
) -> None:
    _, park, _ = await places(user_client)
    await pin(user_client, park)

    verdict = (
        await user_client.get("/api/v1/weather/forecast", params={"location_id": park})
    ).json()["verdict"]

    assert verdict["move_indoors"] is False and verdict["concerns"] == []


async def test_the_forecast_is_cached_per_district_and_hour(
    user_client: AsyncClient, provider: dict[str, Any]
) -> None:
    _, park, _ = await places(user_client)
    await pin(user_client, park)

    for _ in range(3):
        await user_client.get("/api/v1/weather/forecast", params={"location_id": park})

    assert provider["calls"] == [(55.75, 37.62)]


async def test_a_provider_outage_is_a_clear_503(
    user_client: AsyncClient, provider: dict[str, Any]
) -> None:
    _, park, _ = await places(user_client)
    await pin(user_client, park)
    provider["down"] = True

    response = await user_client.get("/api/v1/weather/forecast", params={"location_id": park})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "service_unavailable"


async def test_a_forecast_needs_an_outdoor_place_with_coordinates(
    user_client: AsyncClient, provider: dict[str, Any], client: AsyncClient
) -> None:
    home, park, _ = await places(user_client)
    token = user_client.headers["Authorization"]

    no_pin = await user_client.get("/api/v1/weather/forecast", params={"location_id": park})
    indoor = await user_client.get("/api/v1/weather/forecast", params={"location_id": home})
    assert no_pin.status_code == 422 and "Отметь" in no_pin.json()["detail"]["message"]
    assert indoor.status_code == 422

    stranger = await signed_in(client, "bob")
    other = await stranger.get("/api/v1/weather/forecast", params={"location_id": park})
    assert other.status_code == 404
    assert provider["calls"] == []
    user_client.headers["Authorization"] = token


# --- moving a workout -----------------------------------------------------------------


async def available_at(client: AsyncClient, location_id: str) -> set[str]:
    listed = (await client.get("/api/v1/exercises", params={"location_id": location_id})).json()
    return {e["slug"] for e in listed}


def park_day(program: dict[str, Any], park: str) -> dict[str, Any]:
    return next(s for s in program["weeks"][0]["sessions"] if s["location_id"] == park)


async def give_home_a_band(client: AsyncClient, home: str) -> None:
    response = await client.put(
        f"/api/v1/locations/{home}/equipment",
        json=[
            {"equipment_code": "kettlebell", "details": {"type": "fixed", "weights_kg": ["16"]}},
            {"equipment_code": "chair"},
            {"equipment_code": "towel"},
            {"equipment_code": "resistance_band", "details": {"resistances": ["medium"]}},
        ],
    )
    assert response.status_code == 200, response.text


async def test_a_park_workout_moves_home_with_the_same_patterns(user_client: AsyncClient) -> None:
    home, park, program = await places(user_client)
    # «Подтягивания на площадке → тяга резинки» (docs/01-domain.md).
    await give_home_a_band(user_client, home)
    workout = await start(user_client, planned_session_id=park_day(program, park)["id"])
    before = exercises(workout)

    response = await user_client.post(
        f"/api/v1/sessions/{workout['id']}/swap-location", json={"location_id": home}
    )

    assert response.status_code == 200, response.text
    moved = response.json()
    assert moved["location_id"] == home
    at_home = await available_at(user_client, home)
    assert all(e["exercise_slug"] in at_home for e in exercises(moved))
    assert [e["pattern_code"] for e in exercises(moved)] == [e["pattern_code"] for e in before]
    assert moved["substitutions"]
    assert {s["reason"] for s in moved["substitutions"]} == {"weather"}
    assert "Тренировка собрана под «Дом»" in moved["notes_ru"][-1]


async def test_a_movement_with_nothing_to_do_it_at_home_is_left_out_and_named(
    user_client: AsyncClient,
) -> None:
    home, park, program = await places(user_client)
    workout = await start(user_client, planned_session_id=park_day(program, park)["id"])

    moved = (
        await user_client.post(
            f"/api/v1/sessions/{workout['id']}/swap-location", json={"location_id": home}
        )
    ).json()

    patterns = {e["pattern_code"] for e in exercises(moved)}
    assert "pull_v" not in patterns
    assert "нечем заменить" in moved["notes_ru"][-1]


async def test_what_was_already_done_at_the_park_stays(user_client: AsyncClient) -> None:
    home, park, program = await places(user_client)
    workout = await start(user_client, planned_session_id=park_day(program, park)["id"])
    first = exercises(workout)[0]
    await user_client.post(
        f"/api/v1/sessions/{workout['id']}/sets", json={"sets": [a_set(first, 0)]}
    )

    moved = (
        await user_client.post(
            f"/api/v1/sessions/{workout['id']}/swap-location", json={"location_id": home}
        )
    ).json()

    assert exercises(moved)[0]["exercise_slug"] == first["exercise_slug"]


async def test_starting_a_park_day_at_home_fits_it_to_home(user_client: AsyncClient) -> None:
    home, park, program = await places(user_client)

    workout = await start(
        user_client, planned_session_id=park_day(program, park)["id"], location_id=home
    )

    at_home = await available_at(user_client, home)
    assert all(e["exercise_slug"] in at_home for e in exercises(workout))


async def test_moving_to_someone_elses_place_is_refused(
    user_client: AsyncClient, client: AsyncClient
) -> None:
    _, park, program = await places(user_client)
    workout = await start(user_client, planned_session_id=park_day(program, park)["id"])
    token = user_client.headers["Authorization"]
    stranger = await signed_in(client, "bob")
    strangers_home = (
        await stranger.post("/api/v1/locations", json={"kind": "home", "title": "Чужой дом"})
    ).json()["id"]
    stranger.headers["Authorization"] = token

    response = await stranger.post(
        f"/api/v1/sessions/{workout['id']}/swap-location", json={"location_id": strangers_home}
    )

    assert response.status_code == 422


async def test_weather_is_not_a_reason_to_swap_one_exercise(user_client: AsyncClient) -> None:
    await with_program(user_client)
    workout = await start(user_client)
    response = await user_client.post(
        f"/api/v1/sessions/{workout['id']}/substitute",
        json={"exercise_slug": exercises(workout)[0]["exercise_slug"], "reason": "weather"},
    )
    assert response.status_code == 422
