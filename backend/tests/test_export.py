from typing import Any

import pytest
from httpx import AsyncClient

from app.storage import storage
from tests.conftest import signed_in
from tests.test_sessions import a_set, exercises, start, with_program

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("catalog")]


@pytest.fixture(autouse=True)
def no_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    async def nothing(*_: Any) -> None: ...

    monkeypatch.setattr(storage, "ensure_bucket", nothing)


async def test_the_export_holds_everything_about_the_person(
    user_client: AsyncClient, client: AsyncClient
) -> None:
    await with_program(user_client)
    workout = await start(user_client)
    await user_client.post(
        f"/api/v1/sessions/{workout['id']}/sets",
        json={"sets": [a_set(exercises(workout, "main")[0], 0)]},
    )
    await user_client.post(f"/api/v1/sessions/{workout['id']}/finish", json={"note": "ок"})
    await user_client.post("/api/v1/body/metrics", json={"weight_kg": "80"})
    await user_client.post(
        "/api/v1/body/photos/upload-url", json={"angle": "front", "content_type": "image/jpeg"}
    )
    await user_client.get("/api/v1/progress/skills")
    token = user_client.headers["Authorization"]

    # Someone else's data must never end up in the file.
    stranger = await signed_in(client, "bob")
    await stranger.post("/api/v1/body/metrics", json={"weight_kg": "95"})
    stranger.headers["Authorization"] = token

    response = await stranger.get("/api/v1/export/all")

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith('attachment; filename="selfforge-')
    data = response.json()
    assert data["format_version"] == 1
    assert data["user"]["username"] == "alice"
    assert "hashed_password" not in str(data)
    assert data["profile"]["goal_primary"] == "hypertrophy"
    assert len(data["pattern_levels"]) == 10
    assert len(data["locations"]) == 2
    assert len(data["programs"]) == 1 and data["programs"][0]["weeks"]
    [done] = data["workouts"]
    assert done["note"] == "ок" and len(done["sets"]) == 1
    assert data["personal_records"]
    assert [m["weight_kg"] for m in data["body_metrics"]] == ["80.00"]
    assert len(data["photos"]) == 1 and data["photos"][0]["url"]
    assert {s["skill_slug"] for s in data["skill_progress"]} >= {"first_pullup"}


async def test_the_export_needs_a_sign_in(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/export/all")).status_code == 401
