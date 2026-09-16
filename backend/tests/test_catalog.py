from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Exercise
from app.schemas.catalog import PatternCode
from app.seed import load_catalog, seed

pytestmark = pytest.mark.asyncio

CATALOG = load_catalog()


@pytest.fixture
async def seeded(db_session: AsyncSession) -> None:
    await seed(db_session, CATALOG)


def test_catalog_size_matches_mvp_scope() -> None:
    assert 80 <= len(CATALOG.exercises) <= 120
    assert {pattern for pattern, _ in CATALOG.exercises.values()} == set(PatternCode)


def test_every_ladder_step_leads_somewhere() -> None:
    """Each pattern is one scale: only its top exercises may lack a next step."""
    for code in PatternCode:
        levels = [ex.difficulty_level for p, ex in CATALOG.exercises.values() if p == code]
        for pattern, ex in CATALOG.exercises.values():
            if pattern == code and ex.next_slug is None:
                assert ex.difficulty_level >= max(levels) - 1, ex.slug


def test_load_catalog_reports_broken_references(tmp_path: Path) -> None:
    (tmp_path / "exercises").mkdir()
    (tmp_path / "patterns.yaml").write_text(
        "- {code: squat, title_ru: П, description_ru: П}", encoding="utf-8"
    )
    (tmp_path / "equipment.yaml").write_text("[]", encoding="utf-8")
    (tmp_path / "skills.yaml").write_text("[]", encoding="utf-8")
    (tmp_path / "exercises" / "squat.yaml").write_text(
        """
pattern: squat
exercises:
  - {slug: easy, title_ru: A, difficulty_level: 2, next_slug: hard, primary_muscles: [quads],
     technique_ru: t, common_mistakes_ru: [a, b], required_equipment: [[anvil]]}
  - {slug: hard, title_ru: B, difficulty_level: 1, next_slug: ghost, primary_muscles: [quads],
     technique_ru: t, common_mistakes_ru: [a, b]}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc:
        load_catalog(tmp_path)

    message = str(exc.value)
    assert "easy: unknown equipment 'anvil'" in message
    assert "easy: ladder link 'hard' goes the wrong way" in message
    assert "hard: ladder link to unknown 'ghost'" in message


def test_load_catalog_checks_tonnage_shares_and_skill_goals(tmp_path: Path) -> None:
    (tmp_path / "exercises").mkdir()
    (tmp_path / "patterns.yaml").write_text(
        "- {code: core, title_ru: К, description_ru: К}", encoding="utf-8"
    )
    (tmp_path / "equipment.yaml").write_text("[]", encoding="utf-8")
    (tmp_path / "skills.yaml").write_text(
        """
- {slug: hold, title_ru: H, description_ru: d, lead_up_exercise_slugs: [plank],
   goal: {exercise_slug: plank, reps: 10}}
""",
        encoding="utf-8",
    )
    (tmp_path / "exercises" / "core.yaml").write_text(
        """
pattern: core
exercises:
  - {slug: plank, title_ru: P, difficulty_level: 1, bodyweight_share: 0.5,
     progression_criteria: {sets: 3, hold_seconds: 30}, primary_muscles: [abs],
     technique_ru: t, common_mistakes_ru: [a, b]}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc:
        load_catalog(tmp_path)

    message = str(exc.value)
    assert "plank: timed work has no tonnage" in message
    assert "skill hold: 'plank' is measured in seconds" in message


def test_every_skill_with_an_exercise_of_its_own_has_a_goal() -> None:
    goals = {s.slug: s.goal for s in CATALOG.skills}
    assert goals["ten_pullups"] is not None and goals["ten_pullups"].reps == 10
    assert goals["handstand"] is not None and goals["handstand"].hold_seconds == 30
    # No such exercise in the catalog: these are marked achieved by hand.
    assert goals["pullover"] is None and goals["front_lever"] is None


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    await seed(db_session, CATALOG)
    await seed(db_session, CATALOG)

    count = await db_session.scalar(select(func.count()).select_from(Exercise))
    assert count == len(CATALOG.exercises)


@pytest.mark.usefixtures("seeded")
async def test_list_exercises_with_filters(client: AsyncClient) -> None:
    everything = (await client.get("/api/v1/exercises")).json()
    assert len(everything) == len(CATALOG.exercises)

    pull_v = (await client.get("/api/v1/exercises", params={"pattern": "pull_v"})).json()
    assert pull_v and {e["pattern_code"] for e in pull_v} == {"pull_v"}

    kettlebell = (await client.get("/api/v1/exercises", params={"equipment": "kettlebell"})).json()
    assert kettlebell
    assert all(any("kettlebell" in g for g in e["required_equipment"]) for e in kettlebell)

    bodyweight = (await client.get("/api/v1/exercises", params={"equipment": "none"})).json()
    assert bodyweight and all(e["required_equipment"] == [] for e in bodyweight)

    easy = (await client.get("/api/v1/exercises", params={"difficulty_max": 1})).json()
    assert easy and all(e["difficulty_level"] == 1 for e in easy)


@pytest.mark.usefixtures("seeded")
async def test_get_exercise_detail_and_missing(client: AsyncClient) -> None:
    pullup = (await client.get("/api/v1/exercises/pullup")).json()
    assert pullup["title_ru"] == "Подтягивания"
    assert pullup["prev_slug"] == "negative_pullup"
    assert pullup["progression_criteria"] == {"sets": 3, "reps": 10, "hold_seconds": None}
    assert len(pullup["common_mistakes_ru"]) >= 2

    missing = await client.get("/api/v1/exercises/levitation")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "not_found"


@pytest.mark.usefixtures("seeded")
async def test_ladder_is_ordered_by_difficulty(client: AsyncClient) -> None:
    ladder = (await client.get("/api/v1/patterns/pull_v/ladder")).json()

    assert ladder["pattern"]["code"] == "pull_v"
    levels = [e["difficulty_level"] for e in ladder["exercises"]]
    assert levels == sorted(levels)
    assert ladder["exercises"][0]["slug"] == "band_pulldown"
    assert ladder["exercises"][-1]["slug"] == "muscle_up"


@pytest.mark.usefixtures("seeded")
async def test_reference_lists(client: AsyncClient) -> None:
    patterns = (await client.get("/api/v1/patterns")).json()
    assert [p["code"] for p in patterns] == [p.value for p in PatternCode]

    equipment = (await client.get("/api/v1/equipment")).json()
    assert {"dumbbell", "kettlebell", "pullup_bar"} <= {e["code"] for e in equipment}

    skills = (await client.get("/api/v1/skills")).json()
    assert len(skills) == len(CATALOG.skills)


@pytest.mark.usefixtures("seeded")
async def test_etag_revalidation(client: AsyncClient) -> None:
    first = await client.get("/api/v1/patterns")
    etag = first.headers["etag"]

    cached = await client.get("/api/v1/patterns", headers={"If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.content == b""

    stale = await client.get("/api/v1/patterns", headers={"If-None-Match": '"old"'})
    assert stale.status_code == 200


@pytest.mark.usefixtures("seeded")
async def test_exercises_say_whether_they_are_counted_in_seconds(client: AsyncClient) -> None:
    exercises = {e["slug"]: e for e in (await client.get("/api/v1/exercises")).json()}
    assert exercises["plank"]["timed"] is True
    assert exercises["farmer_carry"]["timed"] is True
    assert exercises["pullup"]["timed"] is False
