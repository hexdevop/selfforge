from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from app.storage import storage
from tests.conftest import signed_in
from tests.test_sessions import a_set, exercises, start, with_program

pytestmark = [pytest.mark.asyncio]

T0 = datetime(2026, 9, 7, 8, tzinfo=UTC)


@pytest.fixture
def storage_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """No object storage in tests: presigned links are signed locally, network calls logged."""
    calls: list[str] = []

    async def ensure_bucket() -> None:
        calls.append("bucket")

    async def delete(key: str) -> None:
        calls.append(f"delete {key}")

    monkeypatch.setattr(storage, "ensure_bucket", ensure_bucket)
    monkeypatch.setattr(storage, "delete", delete)
    return calls


async def weigh(client: AsyncClient, kg: str, days: float, **extra: Any) -> dict[str, Any]:
    body = {"weight_kg": kg, "measured_at": (T0 + timedelta(days=days)).isoformat(), **extra}
    response = await client.post("/api/v1/body/metrics", json=body)
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


# --- metrics --------------------------------------------------------------------------


async def test_weight_comes_back_as_a_seven_day_average(user_client: AsyncClient) -> None:
    await weigh(user_client, "80.0", 0)
    await weigh(user_client, "81.0", 1)
    await weigh(user_client, "79.0", 6)
    await weigh(user_client, "78.0", 7)

    data = (await user_client.get("/api/v1/body/metrics")).json()

    assert [m["weight_kg"] for m in data["items"]] == ["78.00", "79.00", "81.00", "80.00"]
    assert data["weight_trend"] == [
        {"day": "2026-09-07", "weight_kg": "80.00"},
        {"day": "2026-09-08", "weight_kg": "80.50"},
        {"day": "2026-09-13", "weight_kg": "80.00"},
        {"day": "2026-09-14", "weight_kg": "79.33"},
    ]


async def test_tape_measurements_without_a_weighing(user_client: AsyncClient) -> None:
    response = await user_client.post(
        "/api/v1/body/metrics", json={"waist_cm": "82.5", "note": "утром"}
    )

    assert response.status_code == 201
    metric = response.json()
    assert (metric["waist_cm"], metric["weight_kg"], metric["note"]) == ("82.5", None, "утром")
    assert (await user_client.get("/api/v1/body/metrics")).json()["weight_trend"] == []


async def test_an_empty_measurement_is_refused(user_client: AsyncClient) -> None:
    response = await user_client.post("/api/v1/body/metrics", json={"note": "ничего"})
    assert response.status_code == 422
    assert "хотя бы одно" in str(response.json()["detail"]["fields"])


async def test_metrics_filter_by_period(user_client: AsyncClient) -> None:
    for day in (0, 10, 20):
        await weigh(user_client, "80", day)

    since = (T0 + timedelta(days=5)).isoformat()
    until = (T0 + timedelta(days=15)).isoformat()
    data = (
        await user_client.get("/api/v1/body/metrics", params={"from": since, "to": until})
    ).json()

    assert len(data["items"]) == 1


async def test_a_measurement_can_be_deleted_only_by_its_owner(
    user_client: AsyncClient, client: AsyncClient
) -> None:
    metric = await weigh(user_client, "80", 0)
    token = user_client.headers["Authorization"]

    stranger = await signed_in(client, "bob")
    assert (await stranger.delete(f"/api/v1/body/metrics/{metric['id']}")).status_code == 404

    stranger.headers["Authorization"] = token
    assert (await stranger.delete(f"/api/v1/body/metrics/{metric['id']}")).status_code == 204
    assert (await stranger.get("/api/v1/body/metrics")).json()["items"] == []


# --- photos ---------------------------------------------------------------------------


async def test_a_photo_upload_is_a_presigned_form_capped_in_size(
    user_client: AsyncClient, storage_calls: list[str]
) -> None:
    response = await user_client.post(
        "/api/v1/body/photos/upload-url", json={"angle": "front", "content_type": "image/jpeg"}
    )

    assert response.status_code == 201
    data = response.json()
    assert storage_calls == ["bucket"]
    upload = data["upload"]
    assert upload["url"].startswith("http://localhost:9000/progress-photos")
    assert upload["fields"]["key"].endswith(".jpg")
    assert upload["fields"]["Content-Type"] == "image/jpeg"
    assert "policy" in upload["fields"]
    assert data["photo"]["angle"] == "front"
    assert upload["fields"]["key"] in data["photo"]["url"]

    photos = (await user_client.get("/api/v1/body/photos")).json()
    assert [p["id"] for p in photos] == [data["photo"]["id"]]


async def test_only_images_can_be_uploaded(
    user_client: AsyncClient, storage_calls: list[str]
) -> None:
    response = await user_client.post(
        "/api/v1/body/photos/upload-url", json={"angle": "side", "content_type": "text/html"}
    )
    assert response.status_code == 422
    assert storage_calls == []


async def test_deleting_a_photo_removes_the_file_too(
    user_client: AsyncClient, storage_calls: list[str], client: AsyncClient
) -> None:
    upload = (
        await user_client.post(
            "/api/v1/body/photos/upload-url", json={"angle": "back", "content_type": "image/png"}
        )
    ).json()
    photo_id, key = upload["photo"]["id"], upload["upload"]["fields"]["key"]
    token = user_client.headers["Authorization"]

    stranger = await signed_in(client, "bob")
    assert (await stranger.get("/api/v1/body/photos")).json() == []
    assert (await stranger.delete(f"/api/v1/body/photos/{photo_id}")).status_code == 404

    stranger.headers["Authorization"] = token
    assert (await stranger.delete(f"/api/v1/body/photos/{photo_id}")).status_code == 204
    assert storage_calls[-1] == f"delete {key}"
    assert (await stranger.get("/api/v1/body/photos")).json() == []


# --- tonnage with body mass -----------------------------------------------------------


@pytest.mark.usefixtures("catalog")
async def test_workout_tonnage_counts_body_mass_once_weighed(user_client: AsyncClient) -> None:
    await with_program(user_client)
    await user_client.post("/api/v1/body/metrics", json={"weight_kg": "80"})
    workout = await start(user_client)
    bodyweight = next(
        e
        for e in exercises(workout)
        if e["weight_kg"] is None and not e["timed"] and e["exercise_slug"] in _SHARES
    )

    accepted = (
        await user_client.post(
            f"/api/v1/sessions/{workout['id']}/sets",
            json={"sets": [a_set(bodyweight, 0, reps=10)]},
        )
    ).json()

    expected = _SHARES[bodyweight["exercise_slug"]] * 80 * 10
    assert float(accepted["total_tonnage_kg"]) == pytest.approx(expected)


_SHARES = {"air_squat": 0.7, "box_squat": 0.7, "knee_pushup": 0.5, "pushup": 0.65, "glute_bridge": 0.3}
