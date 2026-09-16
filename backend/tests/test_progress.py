import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import signed_in
from tests.test_sessions import start, with_program

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("catalog")]

NOW = datetime.now(UTC)


def s(
    slug: str,
    reps: int,
    days_ago: float = 0,
    index: int = 0,
    weight: str | None = None,
    side: str = "both",
) -> dict[str, Any]:
    return {
        "client_uuid": str(uuid.uuid4()),
        "exercise_slug": slug,
        "set_index": index,
        "reps": reps,
        "weight_kg": weight,
        "side": side,
        "performed_at": (NOW - timedelta(days=days_ago)).isoformat(),
    }


async def workout(client: AsyncClient, *sets: dict[str, Any]) -> None:
    session = await start(client)
    response = await client.post(
        f"/api/v1/sessions/{session['id']}/sets", json={"sets": list(sets)}
    )
    assert response.status_code == 200, response.text
    await client.post(f"/api/v1/sessions/{session['id']}/finish", json={})


@pytest.fixture
async def athlete(user_client: AsyncClient) -> AsyncClient:
    await with_program(user_client)
    return user_client


async def test_summary_counts_weeks_volume_and_records_within_reach(athlete: AsyncClient) -> None:
    await workout(athlete, s("goblet_squat", 10, days_ago=14, weight="16"))
    await workout(athlete, s("pullup", 10, days_ago=7))
    await workout(athlete, s("pullup", 9), s("goblet_squat", 10, index=1, weight="16"))

    summary = (await athlete.get("/api/v1/progress/summary")).json()

    assert summary["week_streak"] == 3
    assert summary["this_week"]["workouts"] == 1
    assert summary["this_week"]["tonnage_kg"] == "160.00"  # no weighing yet: load only
    assert summary["last_workout_at"] is not None
    assert [n["text_ru"] for n in summary["near_records"]] == [
        "«Подтягивания»: до рекорда 1 повтор"
    ]
    assert summary["imbalances"] == 0


async def test_a_new_person_has_an_empty_summary(athlete: AsyncClient) -> None:
    summary = (await athlete.get("/api/v1/progress/summary")).json()
    assert summary["week_streak"] == 0
    assert summary["this_week"]["workouts"] == 0
    assert summary["near_records"] == []


async def test_pattern_progress_continues_across_ladder_steps(athlete: AsyncClient) -> None:
    await workout(athlete, s("negative_pullup", 5, days_ago=14))
    await workout(athlete, s("pullup", 2, days_ago=7))
    await workout(athlete, s("pullup", 4))

    points = (await athlete.get("/api/v1/progress/patterns/pull_v")).json()["points"]

    assert [p["exercise_slug"] for p in points] == ["negative_pullup", "pullup", "pullup"]
    assert points[0]["level"] < points[1]["level"]
    assert [p["result"] for p in points] == [
        {"kind": "reps", "value": "5"},
        {"kind": "reps", "value": "2"},
        {"kind": "reps", "value": "4"},
    ]


async def test_exercise_progress_per_workout(athlete: AsyncClient) -> None:
    await workout(
        athlete,
        s("goblet_squat", 10, days_ago=7, weight="12"),
        s("goblet_squat", 8, days_ago=7, index=1, weight="16"),
    )

    [point] = (await athlete.get("/api/v1/progress/exercises/goblet_squat")).json()["points"]

    assert point["best"] == {"kind": "est_1rm", "value": "20.27"}
    assert point["top_weight_kg"] == "16.00"
    assert point["working_sets"] == 2
    assert point["tonnage_kg"] == "248.00"
    assert (await athlete.get("/api/v1/progress/exercises/nope")).status_code == 404


async def test_tonnage_by_week_with_body_mass_and_by_pattern(athlete: AsyncClient) -> None:
    await athlete.post(
        "/api/v1/body/metrics",
        json={"weight_kg": "80", "measured_at": (NOW - timedelta(days=30)).isoformat()},
    )
    await workout(
        athlete,
        s("pullup", 5, days_ago=7),
        s("db_overhead_press", 10, days_ago=7, index=1, weight="10"),
    )

    weeks = (await athlete.get("/api/v1/progress/tonnage", params={"period": "week"})).json()
    pulls = (await athlete.get("/api/v1/progress/tonnage", params={"pattern": "pull_v"})).json()

    assert [w["tonnage_kg"] for w in weeks] == ["480.00"]  # 0.95·80·5 + 10·10
    assert [w["tonnage_kg"] for w in pulls] == ["380.00"]


async def test_records_newest_first(athlete: AsyncClient) -> None:
    await workout(athlete, s("goblet_squat", 8, days_ago=7, weight="16"))
    await workout(athlete, s("pullup", 5))

    records = (await athlete.get("/api/v1/progress/records")).json()

    assert records[0]["exercise_slug"] == "pullup"
    assert {r["exercise_slug"] for r in records} == {"pullup", "goblet_squat"}


async def test_balance_flags_a_lagging_side(athlete: AsyncClient) -> None:
    await workout(
        athlete,
        s("split_squat", 10, days_ago=3, side="left"),
        s("split_squat", 7, days_ago=3, side="right"),
    )

    [gap] = (await athlete.get("/api/v1/progress/balance")).json()

    assert (gap["exercise_slug"], gap["weaker_side"]) == ("split_squat", "right")
    assert "30%" in gap["advice_ru"]
    assert (await athlete.get("/api/v1/progress/summary")).json()["imbalances"] == 1


# --- skills ---------------------------------------------------------------------------


def by_slug(skills: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {skill["skill_slug"]: skill for skill in skills}


async def test_skills_follow_the_logs(athlete: AsyncClient) -> None:
    await workout(athlete, s("pullup", 3, days_ago=2))

    skills = by_slug((await athlete.get("/api/v1/progress/skills")).json())

    assert skills["first_pullup"]["status"] == "achieved"
    assert skills["first_pullup"]["achieved_at"].startswith(
        (NOW - timedelta(days=2)).date().isoformat()
    )
    ten = skills["ten_pullups"]
    assert ten["status"] == "in_progress"
    assert ten["goal"] == {
        "exercise_slug": "pullup",
        "reps": 10,
        "hold_seconds": None,
        "best": 3,
        "met": False,
    }
    assert ten["current_lead_up_slug"] == "pullup"
    assert skills["muscle_up"]["status"] == "locked"
    assert skills["pullover"]["goal"] is None


async def test_an_achieved_skill_stays_achieved(athlete: AsyncClient) -> None:
    await workout(athlete, s("pullup", 1, days_ago=2))
    first = by_slug((await athlete.get("/api/v1/progress/skills")).json())["first_pullup"]
    await workout(athlete, s("pullup", 0), s("negative_pullup", 3, index=1))

    again = by_slug((await athlete.get("/api/v1/progress/skills")).json())["first_pullup"]

    assert again["status"] == "achieved"
    assert again["achieved_at"] == first["achieved_at"]


async def test_a_skill_without_an_exercise_is_marked_by_hand(athlete: AsyncClient) -> None:
    marked = (await athlete.put("/api/v1/progress/skills/pullover", json={"achieved": True})).json()
    assert marked["status"] == "achieved" and marked["achieved_at"]

    unmarked = (
        await athlete.put("/api/v1/progress/skills/pullover", json={"achieved": False})
    ).json()
    assert unmarked["status"] != "achieved" and unmarked["achieved_at"] is None


async def test_a_skill_earned_in_the_logs_cannot_be_unmarked(athlete: AsyncClient) -> None:
    await workout(athlete, s("pullup", 1))
    await athlete.get("/api/v1/progress/skills")

    response = await athlete.put("/api/v1/progress/skills/first_pullup", json={"achieved": False})

    assert response.status_code == 422
    assert (
        await athlete.put("/api/v1/progress/skills/nope", json={"achieved": True})
    ).status_code == 404


async def test_progress_is_private(athlete: AsyncClient, client: AsyncClient) -> None:
    await workout(athlete, s("pullup", 5))

    stranger = await signed_in(client, "bob")

    assert (await stranger.get("/api/v1/progress/records")).json() == []
    assert (await stranger.get("/api/v1/progress/patterns/pull_v")).json()["points"] == []
    skills = by_slug((await stranger.get("/api/v1/progress/skills")).json())
    assert skills["first_pullup"]["status"] != "achieved"
