from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import signed_in

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("catalog")]

DISCLAIMER = {
    "birth_year": 1990,
    "heart_condition": False,
    "pregnancy": False,
    "recent_injury": False,
    "accepted": True,
}
ANSWERS = {
    "pushups": "6-15",
    "pullups": "0",
    "squats": "10-25",
    "pistol": "no",
    "experienced": False,
    "knows_terms": False,
}


async def onboard(client: AsyncClient, days: int = 3) -> tuple[str, str]:
    """A person with one 16 kg kettlebell at home and a playground nearby."""
    await client.post("/api/v1/profile/disclaimer", json=DISCLAIMER)
    await client.post("/api/v1/profile/assessment", json=ANSWERS)
    await client.patch(
        "/api/v1/profile",
        json={"goal_primary": "hypertrophy", "days_per_week": days, "session_minutes": 45},
    )
    home = (await client.post("/api/v1/locations", json={"kind": "home", "title": "Дом"})).json()
    await client.put(
        f"/api/v1/locations/{home['id']}/equipment",
        json=[
            {"equipment_code": "kettlebell", "details": {"type": "fixed", "weights_kg": ["16"]}},
            {"equipment_code": "chair"},
            {"equipment_code": "towel"},
        ],
    )
    park = (
        await client.post(
            "/api/v1/locations",
            json={"kind": "outdoor_gym", "title": "Площадка", "constraints": {"surface": "sand"}},
        )
    ).json()
    await client.put(
        f"/api/v1/locations/{park['id']}/equipment",
        json=[{"equipment_code": c} for c in ("pullup_bar", "low_bar", "parallel_bars")],
    )
    assert (await client.post("/api/v1/profile/onboarding/complete")).status_code == 200
    return home["id"], park["id"]


def sessions(program: dict[str, Any], week: int = 0) -> list[dict[str, Any]]:
    return program["weeks"][week]["sessions"]  # type: ignore[no-any-return]


async def test_preview_defaults_to_the_default_place_and_saves_nothing(
    user_client: AsyncClient,
) -> None:
    home, _ = await onboard(user_client)

    response = await user_client.post("/api/v1/programs/preview", json={})

    assert response.status_code == 200
    draft = response.json()
    assert draft["structure"] == "fullbody"
    assert draft["weeks_total"] == 4
    assert [w["kind"] for w in draft["weeks"]] == ["accumulation"] * 3 + ["deload"]
    assert {s["location_id"] for s in sessions(draft)} == {home}
    assert all(s["id"] is None for s in sessions(draft))
    first = sessions(draft)[0]["blocks"]
    assert first[0]["kind"] == "warmup" and first[-1]["kind"] == "cooldown"
    assert draft["rationale_ru"]
    assert (await user_client.get("/api/v1/programs/active")).status_code == 404


async def test_preview_follows_the_places_chosen_per_day(user_client: AsyncClient) -> None:
    home, park = await onboard(user_client)

    draft = (
        await user_client.post(
            "/api/v1/programs/preview", json={"day_locations": [home, park, home]}
        )
    ).json()

    assert [s["location_id"] for s in sessions(draft)] == [home, park, home]
    park_day = sessions(draft)[1]
    assert "pull_v" in park_day["focus"]
    assert "гибрид" in draft["rationale_ru"]


async def test_create_saves_the_program_and_replaces_the_active_one(
    user_client: AsyncClient,
) -> None:
    home, park = await onboard(user_client)
    body = {"day_locations": [home, park, home]}
    draft = (await user_client.post("/api/v1/programs/preview", json=body)).json()

    first = await user_client.post("/api/v1/programs", json=body)
    assert first.status_code == 201
    created = first.json()
    assert created["status"] == "active"
    assert all(s["id"] for s in sessions(created))
    # What was previewed is exactly what got saved.
    strip = [[{**s, "id": None} for s in w["sessions"]] for w in created["weeks"]]
    assert strip == [w["sessions"] for w in draft["weeks"]]
    assert created["rationale_ru"] == draft["rationale_ru"]

    active = (await user_client.get("/api/v1/programs/active")).json()
    assert active["id"] == created["id"]

    second = (await user_client.post("/api/v1/programs", json={})).json()
    assert (await user_client.get("/api/v1/programs/active")).json()["id"] == second["id"]
    old = (await user_client.get(f"/api/v1/programs/{created['id']}")).json()
    assert old["status"] == "abandoned"


@pytest.mark.parametrize(
    ("day_locations", "field_message"),
    [
        pytest.param(
            lambda home, park: [home, park], "Нужно место для каждого из 3 дней", id="short"
        ),
        pytest.param(
            lambda home, park: [home, park, "00000000-0000-0000-0000-000000000000"],
            "Такого места нет",
            id="foreign",
        ),
    ],
)
async def test_day_locations_are_validated(
    user_client: AsyncClient, day_locations: Any, field_message: str
) -> None:
    home, park = await onboard(user_client)
    response = await user_client.post(
        "/api/v1/programs/preview", json={"day_locations": day_locations(home, park)}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["fields"]["day_locations"] == field_message


async def test_program_needs_finished_onboarding(user_client: AsyncClient) -> None:
    response = await user_client.post("/api/v1/programs/preview", json={})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "onboarding_incomplete"


async def test_programs_are_private(client: AsyncClient) -> None:
    alice = await signed_in(client, "alice")
    await onboard(alice)
    program = (await alice.post("/api/v1/programs", json={})).json()

    bob = await signed_in(client, "bob")
    assert (await bob.get(f"/api/v1/programs/{program['id']}")).status_code == 404
    home, _ = await onboard(bob)
    foreign = await bob.post("/api/v1/programs/preview", json={"day_locations": [home] * 2})
    assert foreign.status_code == 422


async def test_deleting_a_place_keeps_the_saved_plan_readable(user_client: AsyncClient) -> None:
    home, park = await onboard(user_client)
    await user_client.post("/api/v1/programs", json={"day_locations": [home, park, home]})

    await user_client.delete(f"/api/v1/locations/{park}")

    program = (await user_client.get("/api/v1/programs/active")).json()
    assert [s["location_id"] for s in sessions(program)] == [home, None, home]
