from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("catalog")]

DISCLAIMER = {
    "birth_year": 1995,
    "heart_condition": False,
    "pregnancy": False,
    "recent_injury": False,
    "health_flags": ["knees"],
    "accepted": True,
}
ANSWERS = {
    "pushups": "16-30",
    "pullups": "0",
    "squats": "25-50",
    "pistol": "no",
    "experienced": True,
    "knows_terms": True,
}


def levels_by_pattern(body: list[dict[str, object]]) -> dict[object, dict[str, object]]:
    return {level["pattern_code"]: level for level in body}


async def test_profile_is_created_on_first_read(user_client: AsyncClient) -> None:
    body = (await user_client.get("/api/v1/profile")).json()

    assert body["onboarding_completed_at"] is None
    assert body["guidance_level"] == "normal"
    assert body["health_flags"] == []


async def test_profile_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/profile")).status_code == 401


@pytest.mark.parametrize(
    ("overrides", "needs_clearance"),
    [
        ({}, False),
        ({"heart_condition": True}, True),
        ({"pregnancy": True}, True),
        ({"recent_injury": True}, True),
        ({"birth_year": datetime.now(UTC).year - 60}, True),
    ],
)
async def test_disclaimer_sets_medical_clearance_flag(
    user_client: AsyncClient, overrides: dict[str, object], needs_clearance: bool
) -> None:
    response = await user_client.post(
        "/api/v1/profile/disclaimer", json={**DISCLAIMER, **overrides}
    )

    body = response.json()
    assert body["needs_medical_clearance"] is needs_clearance
    assert body["medical_disclaimer_accepted_at"] is not None
    assert body["health_flags"] == ["knees"]
    assert "heart_condition" not in body


async def test_disclaimer_must_be_accepted(user_client: AsyncClient) -> None:
    response = await user_client.post(
        "/api/v1/profile/disclaimer", json={**DISCLAIMER, "accepted": False}
    )
    assert response.status_code == 422


async def test_assessment_saves_levels_and_guidance(user_client: AsyncClient) -> None:
    body = (await user_client.post("/api/v1/profile/assessment", json=ANSWERS)).json()

    assert body["overall"] == "intermediate"
    assert body["guidance_level"] == "normal"
    levels = levels_by_pattern(body["levels"])
    assert len(levels) == 10
    assert levels["pull_v"]["current_exercise_slug"] == "australian_pullup_high"
    assert levels["push_h"]["current_exercise_slug"] == "decline_pushup"
    assert levels["push_h"]["assessment_source"] == "onboarding"

    profile = (await user_client.get("/api/v1/profile")).json()
    assert profile["guidance_level"] == "normal"


async def test_assessment_shift_overwrites_previous_answer(user_client: AsyncClient) -> None:
    await user_client.post("/api/v1/profile/assessment", json=ANSWERS)
    body = (
        await user_client.post("/api/v1/profile/assessment", json={**ANSWERS, "shift": -1})
    ).json()

    levels = levels_by_pattern(body["levels"])
    assert len(levels) == 10
    assert levels["push_h"]["current_exercise_slug"] == "pushup"


async def test_manual_level_correction(user_client: AsyncClient) -> None:
    await user_client.post("/api/v1/profile/assessment", json=ANSWERS)

    response = await user_client.patch(
        "/api/v1/profile/pattern-levels", json=[{"pattern_code": "pull_v", "estimated_level": 6}]
    )

    levels = levels_by_pattern(response.json())
    assert levels["pull_v"]["current_exercise_slug"] == "pullup"
    assert levels["pull_v"]["assessment_source"] == "manual"
    assert levels["push_h"]["assessment_source"] == "onboarding"


async def test_timezone_is_validated(user_client: AsyncClient) -> None:
    ok = await user_client.patch("/api/v1/profile", json={"timezone": "Asia/Tashkent"})
    assert ok.json()["timezone"] == "Asia/Tashkent"

    bad = await user_client.patch("/api/v1/profile", json={"timezone": "Mars/Olympus"})
    assert bad.json()["detail"]["fields"] == {"timezone": "Неизвестный часовой пояс"}


async def test_goals_must_differ(user_client: AsyncClient) -> None:
    response = await user_client.patch(
        "/api/v1/profile", json={"goal_primary": "strength", "goal_secondary": "strength"}
    )
    assert response.status_code == 422


async def test_onboarding_completes_only_when_every_step_is_done(user_client: AsyncClient) -> None:
    incomplete = await user_client.post("/api/v1/profile/onboarding/complete")
    assert incomplete.status_code == 409
    assert set(incomplete.json()["detail"]["fields"]) == {
        "disclaimer",
        "assessment",
        "goal_primary",
        "days_per_week",
        "session_minutes",
        "locations",
    }

    await user_client.post("/api/v1/profile/disclaimer", json=DISCLAIMER)
    await user_client.post("/api/v1/profile/assessment", json=ANSWERS)
    await user_client.patch(
        "/api/v1/profile",
        json={"goal_primary": "hypertrophy", "days_per_week": 3, "session_minutes": 45},
    )
    await user_client.post("/api/v1/locations", json={"kind": "home", "title": "Дом"})

    done = await user_client.post("/api/v1/profile/onboarding/complete")
    assert done.status_code == 200
    assert done.json()["onboarding_completed_at"] is not None
