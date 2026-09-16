import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationFailedException
from app.engine.analytics import LoggedSet, body_mass_at, set_tonnage
from app.engine.goals import Goal
from app.engine.mesocycle import Block, BlockKind, PlannedDay, PlannedExercise
from app.engine.progression import Performance, Prescription
from app.engine.session import (
    Drill,
    Readiness,
    Session,
    SessionBlock,
    SessionExercise,
    matched_reps,
    prepare_session,
    substitute_exercise,
    trim_session,
)
from app.models.program import PlannedSession
from app.models.user import User
from app.models.workout import PersonalRecord, SetLog, WorkoutSession
from app.repositories.body import BodyMetricRepository
from app.repositories.location import LocationRepository
from app.repositories.workout import (
    PersonalRecordRepository,
    SetLogRepository,
    WorkoutSessionRepository,
)
from app.schemas.pagination import Page, PageParams
from app.schemas.workout import (
    PersonalRecordRead,
    RecordKind,
    SessionFinish,
    SessionStart,
    SessionStatus,
    SetLogRead,
    SetsAccepted,
    SetsBatch,
    SubstituteRequest,
    TrimRequest,
    WorkoutSessionRead,
)
from app.schemas.workout import (
    Readiness as ReadinessIn,
)
from app.services.body import body_weights
from app.services.catalog import CatalogService
from app.services.location import to_engine_location
from app.services.profile import ProfileService
from app.services.program import ProgramService

# Epley (docs/03-engine.md §7). Above this many reps the formula lies, so no record is claimed.
EST_1RM_MAX_REPS = 10
_HISTORY_SESSIONS = 60


def _session_to_json(session: Session) -> dict[str, Any]:
    return {
        "volume_multiplier": str(session.volume_multiplier),
        "notes_ru": list(session.notes_ru),
        "blocks": [
            {
                "kind": b.kind.value,
                "minutes": b.minutes,
                "exercises": [
                    {
                        "exercise_slug": e.exercise,
                        "pattern_code": e.pattern,
                        "sets": e.sets,
                        "target_min": e.target[0],
                        "target_max": e.target[1],
                        "timed": e.timed,
                        "rest_seconds": e.rest_seconds,
                        "rir": e.rir,
                        "unilateral": e.unilateral,
                        "weight_kg": str(e.weight_kg) if e.weight_kg is not None else None,
                        "tempo": e.tempo,
                        "hint_ru": e.hint_ru,
                        "planned_slug": e.planned_slug,
                    }
                    for e in b.exercises
                ],
                "drills": [{"title_ru": d.title_ru, "seconds": d.seconds} for d in b.drills],
            }
            for b in session.blocks
        ],
    }


def _exercise_from_json(data: Mapping[str, Any]) -> SessionExercise:
    weight = data.get("weight_kg")
    return SessionExercise(
        exercise=data["exercise_slug"],
        pattern=data["pattern_code"],
        sets=data["sets"],
        target=(data["target_min"], data["target_max"]),
        timed=data["timed"],
        rest_seconds=data["rest_seconds"],
        rir=data["rir"],
        unilateral=data["unilateral"],
        weight_kg=Decimal(weight) if weight is not None else None,
        tempo=data.get("tempo"),
        hint_ru=data.get("hint_ru", ""),
        planned_slug=data.get("planned_slug", ""),
    )


def _session_from_json(plan: Mapping[str, Any]) -> Session:
    return Session(
        blocks=tuple(
            SessionBlock(
                kind=BlockKind(b["kind"]),
                minutes=b["minutes"],
                exercises=tuple(_exercise_from_json(e) for e in b["exercises"]),
                drills=tuple(Drill(d["title_ru"], d["seconds"]) for d in b["drills"]),
            )
            for b in plan["blocks"]
        ),
        volume_multiplier=Decimal(plan["volume_multiplier"]),
        notes_ru=tuple(plan["notes_ru"]),
    )


def _planned_day(planned: PlannedSession) -> PlannedDay:
    return PlannedDay(
        day_index=planned.day_index,
        location_id=str(planned.location_id) if planned.location_id else "",
        title=planned.title_ru,
        focus=tuple(planned.focus),
        minutes=planned.estimated_minutes,
        blocks=tuple(
            Block(
                kind=BlockKind(b["kind"]),
                minutes=b["minutes"],
                exercises=tuple(
                    PlannedExercise(
                        exercise=e["exercise_slug"],
                        pattern=e["pattern_code"],
                        sets=e["sets"],
                        target=(e["target_min"], e["target_max"]),
                        timed=e["timed"],
                        rest_seconds=e["rest_seconds"],
                        rir=e["rir"],
                        tempo=e.get("tempo"),
                    )
                    for e in b["exercises"]
                ),
            )
            for b in planned.blocks
        ),
    )


def logged_set(log: SetLog) -> LoggedSet:
    return LoggedSet(
        session_id=str(log.session_id),
        exercise=log.exercise_slug,
        set_index=log.set_index,
        performed_at=log.performed_at,
        reps=log.reps,
        side=log.side,
        weight_kg=log.weight_kg,
        added_weight_kg=log.added_weight_kg,
        is_warmup=log.is_warmup,
    )


def _performed(logs: Sequence[SetLog]) -> tuple[int, ...]:
    """Reps per working set. One-sided work counts as the weaker side (§6)."""
    by_index: dict[int, list[SetLog]] = {}
    for log in logs:
        if not log.is_warmup:
            by_index.setdefault(log.set_index, []).append(log)
    done = []
    for index in sorted(by_index):
        sides = by_index[index]
        reps = [s.reps for s in sides]
        done.append(matched_reps(min(reps), max(reps)) if len(sides) > 1 else reps[0])
    return tuple(done)


def _history(
    sessions: Sequence[WorkoutSession], logs: Sequence[SetLog]
) -> dict[str, list[Performance]]:
    """What was actually done in each plan slot, oldest first."""
    by_session: dict[uuid.UUID, list[SetLog]] = {}
    for log in logs:
        by_session.setdefault(log.session_id, []).append(log)

    history: dict[str, list[Performance]] = {}
    for workout in sorted(sessions, key=lambda s: s.started_at):
        plan = workout.plan or {}
        for block in plan.get("blocks", []):
            for entry in block["exercises"]:
                slot = entry.get("planned_slug") or entry["exercise_slug"]
                done = _performed(
                    [
                        s
                        for s in by_session.get(workout.id, ())
                        if s.exercise_slug == entry["exercise_slug"]
                    ]
                )
                if not done:
                    continue
                weight = entry.get("weight_kg")
                history.setdefault(slot, []).append(
                    Performance(
                        Prescription(
                            exercise=entry["exercise_slug"],
                            sets=entry["sets"],
                            target=(entry["target_min"], entry["target_max"]),
                            rest_seconds=entry["rest_seconds"],
                            weight_kg=Decimal(weight) if weight is not None else None,
                            tempo=entry.get("tempo"),
                        ),
                        done,
                    )
                )
    return history


def _records_from(logs: Sequence[SetLog]) -> dict[tuple[str, RecordKind], tuple[Decimal, SetLog]]:
    """The best of each kind inside one batch, before it meets what's already stored."""
    best: dict[tuple[str, RecordKind], tuple[Decimal, SetLog]] = {}

    def offer(log: SetLog, kind: RecordKind, value: Decimal) -> None:
        key = (log.exercise_slug, kind)
        if key not in best or value > best[key][0]:
            best[key] = (value, log)

    for log in logs:
        if log.is_warmup or log.reps <= 0:
            continue
        offer(log, RecordKind.MAX_REPS, Decimal(log.reps))
        loaded = (log.weight_kg or Decimal(0)) + (log.added_weight_kg or Decimal(0))
        if loaded <= 0:
            continue
        offer(log, RecordKind.MAX_WEIGHT, loaded)
        offer(log, RecordKind.MAX_VOLUME, loaded * log.reps)
        if log.reps <= EST_1RM_MAX_REPS:
            offer(log, RecordKind.EST_1RM, loaded * (1 + Decimal(log.reps) / 30))
    return best


class WorkoutService:
    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user
        self.sessions = WorkoutSessionRepository(session)
        self.set_logs = SetLogRepository(session)
        self.records = PersonalRecordRepository(session)

    async def start(self, data: SessionStart) -> WorkoutSessionRead:
        programs = ProgramService(self.session, self.user)
        planned: PlannedSession | None = None
        if not data.unplanned:
            planned = (
                await programs.planned_session(data.planned_session_id)
                if data.planned_session_id
                else await programs.next_planned_session()
            )

        places = LocationRepository(self.session)
        location_id = data.location_id or (planned.location_id if planned else None)
        if location_id is not None:
            location = await places.get_for_user(location_id, self.user.id)
        else:
            # The default place is listed first.
            location = next(iter(await places.list_for_user(self.user.id)), None)
        if location is None:
            raise ValidationFailedException(
                "Выбери место, где будешь тренироваться", {"location_id": "Такого места нет"}
            )

        day = _planned_day(planned) if planned else await programs.one_off_day(location)

        profile = await ProfileService(self.session, self.user).get()
        if profile.goal_primary is None:
            raise ValidationFailedException("Сначала пройди онбординг до конца")

        catalog = await CatalogService(self.session).engine_exercises()
        past = await self.sessions.list(
            {"user_id": self.user.id, "status": SessionStatus.COMPLETED.value},
            PageParams(page=1, size=_HISTORY_SESSIONS),
            order_by=WorkoutSession.started_at.desc(),
        )
        logs = await self.set_logs.for_sessions([s.id for s in past.items])

        prepared = prepare_session(
            day,
            _history(past.items, logs),
            Readiness(data.readiness.sleep, data.readiness.stress, data.readiness.soreness),
            to_engine_location(location),
            catalog,
            Goal(profile.goal_primary),
            frozenset(profile.health_flags),
        )

        # Only one workout runs at a time: an earlier one left open is closed as abandoned.
        if (running := await self.sessions.in_progress(self.user.id)) is not None:
            await self.sessions.update(
                running, status=SessionStatus.ABORTED.value, finished_at=datetime.now(UTC)
            )
            await self.session.flush()

        workout = await self.sessions.create(
            user_id=self.user.id,
            planned_session_id=planned.id if planned else None,
            location_id=location.id,
            started_at=datetime.now(UTC),
            status=SessionStatus.IN_PROGRESS.value,
            readiness=data.readiness.model_dump(mode="json"),
            plan=_session_to_json(prepared),
        )
        await self.session.commit()
        return await self.get(workout.id)

    async def get(self, session_id: uuid.UUID) -> WorkoutSessionRead:
        return await self._read(await self._own(session_id))

    async def history(
        self, pagination: PageParams, status: SessionStatus | None = None
    ) -> Page[WorkoutSessionRead]:
        page = await self.sessions.history(self.user.id, pagination, status)
        items = [await self._read(workout) for workout in page.items]
        return Page[WorkoutSessionRead](
            items=items, total=page.total, page=page.page, size=page.size, pages=page.pages
        )

    async def log_sets(self, session_id: uuid.UUID, batch: SetsBatch) -> SetsAccepted:
        workout = await self._running(session_id)
        patterns = {
            e.slug: e.pattern for e in await CatalogService(self.session).engine_exercises()
        }
        unknown = {s.exercise_slug for s in batch.sets} - patterns.keys()
        if unknown:
            raise ValidationFailedException(
                fields={"sets": f"Неизвестные упражнения: {', '.join(sorted(unknown))}"}
            )

        stored = await self.set_logs.add_batch(
            [
                {
                    "client_uuid": s.client_uuid,
                    "session_id": workout.id,
                    "user_id": self.user.id,
                    "exercise_slug": s.exercise_slug,
                    "pattern_code": patterns[s.exercise_slug],
                    "set_index": s.set_index,
                    "side": s.side.value,
                    "weight_kg": s.weight_kg,
                    "added_weight_kg": s.added_weight_kg,
                    "band": s.band,
                    "reps": s.reps,
                    "tempo": s.tempo,
                    "rir": s.rir,
                    "effort_label": s.effort_label.value if s.effort_label else None,
                    "is_warmup": s.is_warmup,
                    "performed_at": s.performed_at,
                }
                for s in batch.sets
            ]
        )
        records = await self._update_records(stored)
        all_logs = await self.set_logs.for_session(workout.id)
        tonnage = await self._tonnage(all_logs)
        await self.sessions.update(workout, total_tonnage_kg=tonnage)
        await self.session.commit()
        return SetsAccepted(
            accepted=[s.client_uuid for s in batch.sets],
            records=[PersonalRecordRead.model_validate(r) for r in records],
            total_tonnage_kg=tonnage,
        )

    async def substitute(
        self, session_id: uuid.UUID, data: SubstituteRequest
    ) -> WorkoutSessionRead:
        workout = await self._running(session_id)
        prepared = _session_from_json(workout.plan)
        current = next(
            (e for b in prepared.blocks for e in b.exercises if e.exercise == data.exercise_slug),
            None,
        )
        if current is None:
            raise ValidationFailedException(
                fields={"exercise_slug": "Этого движения нет в тренировке"}
            )

        location = (
            await LocationRepository(self.session).get_for_user(workout.location_id, self.user.id)
            if workout.location_id
            else None
        )
        if location is None:
            raise ValidationFailedException("Место тренировки больше не существует")

        profile = await ProfileService(self.session, self.user).get()
        catalog = await CatalogService(self.session).engine_exercises()
        replacement = substitute_exercise(
            current,
            data.reason,
            to_engine_location(location),
            catalog,
            Goal(profile.goal_primary or Goal.HEALTH),
            used={e.exercise for b in prepared.blocks for e in b.exercises},
            health_flags=frozenset(profile.health_flags),
        )
        if replacement is None:
            raise ValidationFailedException(
                "Здесь нечем заменить это движение — можно пропустить его сегодня"
            )

        swapped = Session(
            blocks=tuple(
                SessionBlock(
                    b.kind,
                    b.minutes,
                    tuple(replacement if e is current else e for e in b.exercises),
                    b.drills,
                )
                for b in prepared.blocks
            ),
            volume_multiplier=prepared.volume_multiplier,
            notes_ru=prepared.notes_ru,
        )
        await self.sessions.update(
            workout,
            plan=_session_to_json(swapped),
            substitutions=[
                *workout.substitutions,
                {
                    "from_slug": current.exercise,
                    "to_slug": replacement.exercise,
                    "reason": data.reason.value,
                    "at": datetime.now(UTC).isoformat(),
                },
            ],
        )
        await self.session.commit()
        return await self.get(workout.id)

    async def trim(self, session_id: uuid.UUID, data: TrimRequest) -> WorkoutSessionRead:
        workout = await self._running(session_id)
        trimmed = trim_session(_session_from_json(workout.plan), data.minutes_left)
        await self.sessions.update(workout, plan=_session_to_json(trimmed))
        await self.session.commit()
        return await self.get(workout.id)

    async def finish(self, session_id: uuid.UUID, data: SessionFinish) -> WorkoutSessionRead:
        workout = await self._running(session_id)
        logs = await self.set_logs.for_session(workout.id)
        await self.sessions.update(
            workout,
            status=SessionStatus.COMPLETED.value,
            finished_at=datetime.now(UTC),
            total_tonnage_kg=await self._tonnage(logs),
            note=data.note,
        )
        await self.session.commit()
        return await self.get(workout.id)

    async def abort(self, session_id: uuid.UUID) -> WorkoutSessionRead:
        workout = await self._running(session_id)
        await self.sessions.update(
            workout, status=SessionStatus.ABORTED.value, finished_at=datetime.now(UTC)
        )
        await self.session.commit()
        return await self.get(workout.id)

    async def _tonnage(self, logs: Sequence[SetLog]) -> Decimal:
        """Kilograms moved: external load plus each exercise's share of body mass
        (docs/03-engine.md §7), with the body mass of the last weighing."""
        catalog = {e.slug: e for e in await CatalogService(self.session).engine_exercises()}
        metrics = await BodyMetricRepository(self.session).for_user(self.user.id)
        weights = body_weights(list(metrics))
        total = Decimal(0)
        for log in logs:
            if (exercise := catalog.get(log.exercise_slug)) is not None:
                logged = logged_set(log)
                total += set_tonnage(logged, exercise, body_mass_at(log.performed_at, weights))
        return total

    async def _update_records(self, logs: Sequence[SetLog]) -> list[PersonalRecord]:
        if not logs:
            return []
        stored = {(r.exercise_slug, r.kind): r for r in await self.records.for_user(self.user.id)}
        beaten: list[PersonalRecord] = []
        for (slug, kind), (value, log) in _records_from(logs).items():
            value = value.quantize(Decimal("0.01"))
            existing = stored.get((slug, kind.value))
            if existing is not None and existing.value >= value:
                continue
            if existing is not None:
                beaten.append(
                    await self.records.update(
                        existing, value=value, achieved_at=log.performed_at, set_log_id=log.id
                    )
                )
            else:
                beaten.append(
                    await self.records.create(
                        user_id=self.user.id,
                        exercise_slug=slug,
                        pattern_code=log.pattern_code,
                        kind=kind.value,
                        value=value,
                        achieved_at=log.performed_at,
                        set_log_id=log.id,
                    )
                )
        return beaten

    async def _own(self, session_id: uuid.UUID) -> WorkoutSession:
        workout = await self.sessions.get_for_user(session_id, self.user.id)
        if workout is None:
            raise NotFoundException("Такой тренировки нет")
        return workout

    async def _running(self, session_id: uuid.UUID) -> WorkoutSession:
        workout = await self._own(session_id)
        if workout.status != SessionStatus.IN_PROGRESS.value:
            raise ValidationFailedException("Эта тренировка уже завершена")
        return workout

    async def _read(self, workout: WorkoutSession) -> WorkoutSessionRead:
        plan = workout.plan or {"blocks": [], "notes_ru": []}
        return WorkoutSessionRead(
            id=workout.id,
            planned_session_id=workout.planned_session_id,
            location_id=workout.location_id,
            status=SessionStatus(workout.status),
            started_at=workout.started_at,
            finished_at=workout.finished_at,
            readiness=ReadinessIn.model_validate(workout.readiness or {}),
            blocks=plan["blocks"],
            notes_ru=plan["notes_ru"],
            substitutions=workout.substitutions,
            total_tonnage_kg=workout.total_tonnage_kg,
            note=workout.note,
            sets=[SetLogRead.model_validate(s) for s in workout.sets],
        )
