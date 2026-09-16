import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import signed_in
from tests.test_programs import onboard

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("catalog")]


async def with_program(client: AsyncClient, days: int = 3) -> dict[str, Any]:
    home, park = await onboard(client, days)
    body = {"day_locations": [home, park, home][:days]}
    return (await client.post("/api/v1/programs", json=body)).json()  # type: ignore[no-any-return]


def exercises(session: dict[str, Any], kind: str | None = None) -> list[dict[str, Any]]:
    return [
        e
        for block in session["blocks"]
        if kind in (None, block["kind"])
        for e in block["exercises"]
    ]


def a_set(
    exercise: dict[str, Any], index: int, reps: int | None = None, **extra: Any
) -> dict[str, Any]:
    return {
        "client_uuid": str(uuid.uuid4()),
        "exercise_slug": exercise["exercise_slug"],
        "set_index": index,
        "reps": reps if reps is not None else exercise["target_max"],
        "weight_kg": exercise["weight_kg"],
        "performed_at": (datetime.now(UTC) + timedelta(seconds=index)).isoformat(),
        **extra,
    }


async def start(client: AsyncClient, **body: Any) -> dict[str, Any]:
    response = await client.post("/api/v1/sessions", json=body)
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


# --- starting ------------------------------------------------------------------------


async def test_next_session_is_the_first_day_without_a_finished_workout(
    user_client: AsyncClient,
) -> None:
    program = await with_program(user_client)
    days = [d for w in program["weeks"] for d in w["sessions"]]

    first = (await user_client.get("/api/v1/programs/active/next-session")).json()
    assert first["id"] == days[0]["id"]

    workout = await start(user_client)
    assert workout["planned_session_id"] == days[0]["id"]
    await user_client.post(f"/api/v1/sessions/{workout['id']}/finish", json={})

    assert (await user_client.get("/api/v1/programs/active/next-session")).json()["id"] == days[1][
        "id"
    ]


async def test_starting_prepares_the_day_with_weights_warmup_and_cooldown(
    user_client: AsyncClient,
) -> None:
    program = await with_program(user_client)
    day = program["weeks"][0]["sessions"][0]

    workout = await start(user_client)

    assert workout["status"] == "in_progress"
    assert workout["location_id"] == day["location_id"]
    kinds = [b["kind"] for b in workout["blocks"]]
    assert kinds[0] == "warmup" and kinds[-1] == "cooldown"
    assert workout["blocks"][0]["drills"] and workout["blocks"][-1]["drills"]
    assert exercises(workout, "main")
    for e in exercises(workout):
        assert e["hint_ru"]
        assert e["planned_slug"]
        if e["weight_kg"] is not None:
            assert e["weight_kg"] == "16.00"


async def test_a_program_is_required_before_a_workout(user_client: AsyncClient) -> None:
    await onboard(user_client)
    response = await user_client.post("/api/v1/sessions", json={})
    assert response.status_code == 422
    assert "программу" in response.json()["detail"]["message"]


async def test_starting_again_closes_the_workout_left_open(user_client: AsyncClient) -> None:
    await with_program(user_client)
    first = await start(user_client)

    second = await start(user_client)

    assert second["id"] != first["id"]
    abandoned = (await user_client.get(f"/api/v1/sessions/{first['id']}")).json()
    assert abandoned["status"] == "aborted" and abandoned["finished_at"]


async def test_readiness_below_normal_trims_the_extras(user_client: AsyncClient) -> None:
    await with_program(user_client)
    normal = await start(user_client)
    tired = await start(user_client, readiness={"sleep": "bad", "stress": "bad", "soreness": "bad"})

    assert tired["readiness"]["sleep"] == "bad"
    assert tired["notes_ru"]
    assert sum(e["sets"] for e in exercises(tired)) < sum(e["sets"] for e in exercises(normal))
    assert [e["sets"] for e in exercises(tired, "main")] == [
        e["sets"] for e in exercises(normal, "main")
    ]


async def test_workouts_are_private(user_client: AsyncClient, client: AsyncClient) -> None:
    await with_program(user_client)
    workout = await start(user_client)

    stranger = await signed_in(client, "bob")
    assert (await stranger.get(f"/api/v1/sessions/{workout['id']}")).status_code == 404


# --- logging sets ---------------------------------------------------------------------


async def test_the_same_batch_sent_twice_lands_once(user_client: AsyncClient) -> None:
    await with_program(user_client)
    workout = await start(user_client)
    first = exercises(workout, "main")[0]
    batch = {"sets": [a_set(first, 0), a_set(first, 1)]}

    one = await user_client.post(f"/api/v1/sessions/{workout['id']}/sets", json=batch)
    two = await user_client.post(f"/api/v1/sessions/{workout['id']}/sets", json=batch)

    assert one.status_code == 200 and two.status_code == 200
    assert one.json()["accepted"] == two.json()["accepted"]
    stored = (await user_client.get(f"/api/v1/sessions/{workout['id']}")).json()["sets"]
    assert len(stored) == 2
    assert one.json()["total_tonnage_kg"] == two.json()["total_tonnage_kg"]


async def test_tonnage_counts_working_sets_only(user_client: AsyncClient) -> None:
    await with_program(user_client)
    workout = await start(user_client)
    loaded = next(e for e in exercises(workout) if e["weight_kg"] is not None)

    body = {
        "sets": [
            a_set(loaded, 0, reps=10, is_warmup=True),
            a_set(loaded, 1, reps=10),
            a_set(loaded, 2, reps=5),
        ]
    }
    accepted = (await user_client.post(f"/api/v1/sessions/{workout['id']}/sets", json=body)).json()

    assert accepted["total_tonnage_kg"] == "240.00"  # 16 × (10 + 5)


async def test_beating_a_record_is_reported_once(user_client: AsyncClient) -> None:
    await with_program(user_client)
    workout = await start(user_client)
    loaded = next(e for e in exercises(workout) if e["weight_kg"] is not None)

    first = (
        await user_client.post(
            f"/api/v1/sessions/{workout['id']}/sets", json={"sets": [a_set(loaded, 0, reps=8)]}
        )
    ).json()
    kinds = {r["kind"] for r in first["records"]}
    assert {"max_weight", "max_reps", "est_1rm", "max_volume"} <= kinds

    same = (
        await user_client.post(
            f"/api/v1/sessions/{workout['id']}/sets", json={"sets": [a_set(loaded, 1, reps=6)]}
        )
    ).json()
    assert same["records"] == []

    better = (
        await user_client.post(
            f"/api/v1/sessions/{workout['id']}/sets", json={"sets": [a_set(loaded, 2, reps=12)]}
        )
    ).json()
    assert {r["kind"] for r in better["records"]} == {"max_reps", "max_volume"}


async def test_an_unknown_exercise_is_refused(user_client: AsyncClient) -> None:
    await with_program(user_client)
    workout = await start(user_client)
    body = {"sets": [{**a_set(exercises(workout, "main")[0], 0), "exercise_slug": "nope"}]}

    response = await user_client.post(f"/api/v1/sessions/{workout['id']}/sets", json=body)

    assert response.status_code == 422
    assert "nope" in response.json()["detail"]["fields"]["sets"]


async def test_a_finished_workout_takes_no_more_sets(user_client: AsyncClient) -> None:
    await with_program(user_client)
    workout = await start(user_client)
    first = exercises(workout, "main")[0]
    await user_client.post(f"/api/v1/sessions/{workout['id']}/finish", json={"note": "хорошо"})

    response = await user_client.post(
        f"/api/v1/sessions/{workout['id']}/sets", json={"sets": [a_set(first, 0)]}
    )

    assert response.status_code == 422


# --- progression across workouts ------------------------------------------------------


async def test_topping_the_range_makes_the_next_workout_harder(user_client: AsyncClient) -> None:
    await with_program(user_client)
    workout = await start(user_client)
    first = exercises(workout, "main")[0]
    await user_client.post(
        f"/api/v1/sessions/{workout['id']}/sets",
        json={"sets": [a_set(first, i) for i in range(first["sets"])]},
    )
    await user_client.post(f"/api/v1/sessions/{workout['id']}/finish", json={})

    later = await start(user_client, planned_session_id=workout["planned_session_id"])
    same_slot = next(e for e in exercises(later) if e["planned_slug"] == first["planned_slug"])

    assert "Первый раз" not in same_slot["hint_ru"]
    harder = (
        same_slot["exercise_slug"] != first["exercise_slug"]
        or same_slot["sets"] > first["sets"]
        or same_slot["tempo"] != first["tempo"]
        or (same_slot["weight_kg"] or "0") > (first["weight_kg"] or "0")
    )
    assert harder, same_slot


async def test_one_sided_work_is_counted_by_the_weaker_side(user_client: AsyncClient) -> None:
    await with_program(user_client)
    workout = await start(user_client)
    one_sided = next((e for e in exercises(workout) if e["unilateral"]), None)
    if one_sided is None:
        pytest.skip("this plan has no one-sided exercise")

    await user_client.post(
        f"/api/v1/sessions/{workout['id']}/sets",
        json={
            "sets": [
                a_set(one_sided, i, reps=reps, side=side)
                for i in range(one_sided["sets"])
                for side, reps in (("left", one_sided["target_min"]), ("right", 50))
            ]
        },
    )
    await user_client.post(f"/api/v1/sessions/{workout['id']}/finish", json={})

    later = await start(user_client, planned_session_id=workout["planned_session_id"])
    same_slot = next(e for e in exercises(later) if e["planned_slug"] == one_sided["planned_slug"])
    # The strong side's 50 reps must not read as topping the range.
    assert same_slot["exercise_slug"] == one_sided["exercise_slug"]
    assert same_slot["weight_kg"] == one_sided["weight_kg"]


# --- substitution and trimming --------------------------------------------------------


async def test_substituting_swaps_the_movement_and_records_why(user_client: AsyncClient) -> None:
    await with_program(user_client)
    workout = await start(user_client)
    current = exercises(workout, "main")[0]

    response = await user_client.post(
        f"/api/v1/sessions/{workout['id']}/substitute",
        json={"exercise_slug": current["exercise_slug"], "reason": "equipment_busy"},
    )

    assert response.status_code == 200
    updated = response.json()
    slugs = [e["exercise_slug"] for e in exercises(updated)]
    assert current["exercise_slug"] not in slugs
    swapped = next(e for e in exercises(updated) if e["planned_slug"] == current["planned_slug"])
    assert swapped["pattern_code"] == current["pattern_code"]
    assert swapped["hint_ru"]
    assert updated["substitutions"] == [
        {
            "from_slug": current["exercise_slug"],
            "to_slug": swapped["exercise_slug"],
            "reason": "equipment_busy",
            "at": updated["substitutions"][0]["at"],
        }
    ]


async def test_substituting_something_not_in_the_workout_is_refused(
    user_client: AsyncClient,
) -> None:
    await with_program(user_client)
    workout = await start(user_client)

    response = await user_client.post(
        f"/api/v1/sessions/{workout['id']}/substitute",
        json={"exercise_slug": "air-squat", "reason": "pain"},
    )

    assert response.status_code == 422


async def test_trimming_fits_the_time_left_and_keeps_the_main_work(
    user_client: AsyncClient,
) -> None:
    await with_program(user_client)
    workout = await start(user_client)
    before = exercises(workout, "main")

    trimmed = (
        await user_client.post(f"/api/v1/sessions/{workout['id']}/trim", json={"minutes_left": 15})
    ).json()

    assert [e["exercise_slug"] for e in exercises(trimmed, "main")] == [
        e["exercise_slug"] for e in before
    ]
    assert trimmed["blocks"][0]["kind"] == "warmup"
    assert sum(b["minutes"] for b in trimmed["blocks"]) <= sum(
        b["minutes"] for b in workout["blocks"]
    )
    assert trimmed["notes_ru"][-1]


# --- finishing and history ------------------------------------------------------------


async def test_finishing_stores_the_note_and_freezes_the_tonnage(
    user_client: AsyncClient,
) -> None:
    await with_program(user_client)
    workout = await start(user_client)
    loaded = next(e for e in exercises(workout) if e["weight_kg"] is not None)
    await user_client.post(
        f"/api/v1/sessions/{workout['id']}/sets", json={"sets": [a_set(loaded, 0, reps=10)]}
    )

    finished = (
        await user_client.post(
            f"/api/v1/sessions/{workout['id']}/finish", json={"note": "тяжело, но сделал"}
        )
    ).json()

    assert finished["status"] == "completed"
    assert finished["finished_at"]
    assert finished["note"] == "тяжело, но сделал"
    assert finished["total_tonnage_kg"] == "160.00"


async def test_aborting_keeps_what_was_logged(user_client: AsyncClient) -> None:
    await with_program(user_client)
    workout = await start(user_client)
    first = exercises(workout, "main")[0]
    await user_client.post(
        f"/api/v1/sessions/{workout['id']}/sets", json={"sets": [a_set(first, 0)]}
    )

    aborted = (await user_client.post(f"/api/v1/sessions/{workout['id']}/abort")).json()

    assert aborted["status"] == "aborted"
    assert len(aborted["sets"]) == 1


async def test_history_lists_workouts_newest_first(user_client: AsyncClient) -> None:
    await with_program(user_client)
    first = await start(user_client)
    await user_client.post(f"/api/v1/sessions/{first['id']}/finish", json={})
    second = await start(user_client)

    page = (await user_client.get("/api/v1/sessions")).json()

    assert page["total"] == 2
    assert [item["id"] for item in page["items"]] == [second["id"], first["id"]]


# --- unplanned workouts and resuming --------------------------------------------------


async def test_an_unplanned_workout_is_a_full_day_at_the_chosen_place(
    user_client: AsyncClient,
) -> None:
    program = await with_program(user_client)
    park = next(
        s["location_id"]
        for w in program["weeks"]
        for s in w["sessions"]
        if s["location_id"] != program["weeks"][0]["sessions"][0]["location_id"]
    )

    workout = await start(user_client, unplanned=True, location_id=park)

    assert workout["planned_session_id"] is None
    assert workout["location_id"] == park
    kinds = [b["kind"] for b in workout["blocks"]]
    assert kinds[0] == "warmup" and "main" in kinds and kinds[-1] == "cooldown"
    catalog = {
        e["slug"]: e
        for e in (await user_client.get(f"/api/v1/exercises?location_id={park}")).json()
    }
    assert all(e["exercise_slug"] in catalog for e in exercises(workout))


async def test_an_unplanned_workout_does_not_move_the_program_on(
    user_client: AsyncClient,
) -> None:
    await with_program(user_client)
    before = (await user_client.get("/api/v1/programs/active/next-session")).json()

    workout = await start(user_client, unplanned=True)
    await user_client.post(f"/api/v1/sessions/{workout['id']}/finish", json={})

    after = (await user_client.get("/api/v1/programs/active/next-session")).json()
    assert after["id"] == before["id"]


async def test_an_unplanned_workout_needs_no_program(user_client: AsyncClient) -> None:
    home, _ = await onboard(user_client)

    workout = await start(user_client, unplanned=True)

    assert workout["location_id"] == home
    assert exercises(workout, "main")


async def test_a_workout_left_open_can_be_found_to_resume(user_client: AsyncClient) -> None:
    await with_program(user_client)
    done = await start(user_client)
    await user_client.post(f"/api/v1/sessions/{done['id']}/finish", json={})
    running = await start(user_client)

    page = (await user_client.get("/api/v1/sessions?status=in_progress")).json()

    assert [item["id"] for item in page["items"]] == [running["id"]]
