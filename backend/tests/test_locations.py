from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import signed_in

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("catalog")]

ONE_KETTLEBELL = [
    {"equipment_code": "kettlebell", "details": {"type": "fixed", "weights_kg": ["16"]}},
    {"equipment_code": "chair"},
    {"equipment_code": "wall"},
]
ADJUSTABLE_BARBELL = {
    "equipment_code": "barbell",
    "details": {
        "type": "adjustable",
        "bar_kg": "2.5",
        "plates": [{"kg": "5", "count": 2}, {"kg": "2.5", "count": 4}],
    },
}


async def create_home(client: AsyncClient, **extra: Any) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/locations", json={"kind": "home", "title": "Дом", **extra}
    )
    assert response.status_code == 201
    return response.json()  # type: ignore[no-any-return]


async def put_equipment(client: AsyncClient, location_id: str, items: list[Any]) -> Any:
    return await client.put(f"/api/v1/locations/{location_id}/equipment", json=items)


async def test_first_location_becomes_default(user_client: AsyncClient) -> None:
    home = await create_home(user_client)
    park = (
        await user_client.post(
            "/api/v1/locations",
            json={"kind": "outdoor_gym", "title": "Площадка", "constraints": {"surface": "sand"}},
        )
    ).json()

    assert home["is_default"] is True
    assert park["is_default"] is False

    await user_client.patch(f"/api/v1/locations/{park['id']}", json={"is_default": True})
    listed = (await user_client.get("/api/v1/locations")).json()
    assert [(loc["title"], loc["is_default"]) for loc in listed] == [
        ("Площадка", True),
        ("Дом", False),
    ]


async def test_equipment_changes_available_exercises(user_client: AsyncClient) -> None:
    home = await create_home(user_client)
    bodyweight_only = home["available_exercise_count"]

    body = (await put_equipment(user_client, home["id"], ONE_KETTLEBELL)).json()

    assert body["available_exercise_count"] > bodyweight_only
    assert {e["equipment_code"] for e in body["equipment"]} == {"kettlebell", "chair", "wall"}

    listed = await user_client.get(
        "/api/v1/exercises", params={"location_id": home["id"], "pattern": "squat"}
    )
    slugs = {e["slug"] for e in listed.json()}
    assert "goblet_squat" in slugs
    assert "double_kb_front_squat" not in slugs
    assert "barbell_back_squat" not in slugs


async def test_health_flags_reduce_available_exercises(user_client: AsyncClient) -> None:
    home = await create_home(user_client)
    await put_equipment(user_client, home["id"], ONE_KETTLEBELL)
    before = (await user_client.get("/api/v1/locations")).json()[0]["available_exercise_count"]

    await user_client.patch("/api/v1/profile", json={"health_flags": ["knees", "shoulders"]})

    after = (await user_client.get("/api/v1/locations")).json()[0]["available_exercise_count"]
    assert after < before


async def test_constraints_filter_exercises(user_client: AsyncClient) -> None:
    home = await create_home(user_client, constraints={"quiet_mode": True})
    listed = (await user_client.get("/api/v1/exercises", params={"location_id": home["id"]})).json()
    assert "burpee" not in {e["slug"] for e in listed}


async def test_location_filter_requires_sign_in(
    user_client: AsyncClient, client: AsyncClient
) -> None:
    home = await create_home(user_client)
    del client.headers["Authorization"]
    response = await client.get("/api/v1/exercises", params={"location_id": home["id"]})
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("items", "field"),
    [
        ([{"equipment_code": "anvil"}], "anvil"),
        ([{"equipment_code": "kettlebell"}], "kettlebell"),
        ([{"equipment_code": "dumbbell", "details": {"type": "fixed"}}], "dumbbell"),
        ([{"equipment_code": "barbell", "details": {"bar_kg": "20"}}], "barbell"),
        ([{"equipment_code": "bench", "quantity": 2}], "bench"),
        ([{"equipment_code": "chair"}, {"equipment_code": "chair"}], "chair"),
    ],
)
async def test_invalid_equipment_is_rejected_with_field_errors(
    user_client: AsyncClient, items: list[Any], field: str
) -> None:
    home = await create_home(user_client)
    response = await put_equipment(user_client, home["id"], items)

    assert response.status_code == 422
    assert field in response.json()["detail"]["fields"]


async def test_weight_grid_and_plate_calculator(user_client: AsyncClient) -> None:
    home = await create_home(user_client)
    await put_equipment(user_client, home["id"], [ADJUSTABLE_BARBELL, *ONE_KETTLEBELL])

    grids = {
        g["equipment_code"]: g
        for g in (await user_client.get(f"/api/v1/locations/{home['id']}/weight-grid")).json()
    }
    assert grids["kettlebell"]["weights_kg"] == ["16.00"]
    assert grids["barbell"]["weights_kg"][:3] == ["2.50", "7.50", "12.50"]
    assert grids["barbell"]["min_step_kg"] == "5.00"

    plates_url = f"/api/v1/locations/{home['id']}/plates"
    ok = (
        await user_client.post(plates_url, json={"equipment_code": "barbell", "target_kg": "17.5"})
    ).json()
    assert ok["achievable"] is True
    assert ok["per_side"] == [{"kg": "5.00", "count": 1}, {"kg": "2.50", "count": 1}]

    off = (
        await user_client.post(plates_url, json={"equipment_code": "barbell", "target_kg": "15"})
    ).json()
    assert off["achievable"] is False
    assert off["nearest_kg"] == ["12.50", "17.50"]


async def test_other_users_locations_are_invisible(
    user_client: AsyncClient, client: AsyncClient
) -> None:
    home = await create_home(user_client)
    await signed_in(client, "bob")

    assert (await client.get("/api/v1/locations")).json() == []
    response = await client.patch(f"/api/v1/locations/{home['id']}", json={"title": "Моё"})
    assert response.status_code == 404


async def test_delete_location(user_client: AsyncClient) -> None:
    home = await create_home(user_client)
    await put_equipment(user_client, home["id"], ONE_KETTLEBELL)

    assert (await user_client.delete(f"/api/v1/locations/{home['id']}")).status_code == 204
    assert (await user_client.get("/api/v1/locations")).json() == []
