from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationFailedException
from app.engine import analytics
from app.engine.analytics import LoggedSet, Period, Result, SkillStatus, Target
from app.engine.types import CatalogExercise
from app.models.body import SkillProgress
from app.models.catalog import Skill
from app.models.user import User
from app.repositories.body import BodyMetricRepository, SkillProgressRepository
from app.repositories.catalog import CatalogRepository
from app.repositories.workout import PersonalRecordRepository, SetLogRepository
from app.schemas.catalog import PatternCode
from app.schemas.progress import (
    ExercisePoint,
    ExerciseProgress,
    ImbalanceRead,
    NearRecordRead,
    PatternPoint,
    PatternProgress,
    ResultRead,
    SkillProgressRead,
    Summary,
    TargetRead,
    TonnagePoint,
    TonnageQuery,
    WeekRead,
)
from app.schemas.workout import PersonalRecordRead
from app.services.body import body_weights
from app.services.catalog import CatalogService
from app.services.profile import ProfileService
from app.services.workout import logged_set


def _result(result: Result | None) -> ResultRead | None:
    return ResultRead(kind=result.kind, value=result.value) if result else None


def _skill(skill: Skill) -> analytics.Skill:
    def target(data: dict[str, object]) -> Target:
        reps, hold = data.get("reps"), data.get("hold_seconds")
        return Target(
            exercise=str(data["exercise_slug"]),
            reps=int(str(reps)) if reps is not None else None,
            hold_seconds=int(str(hold)) if hold is not None else None,
        )

    return analytics.Skill(
        slug=skill.slug,
        goal=target(skill.goal) if skill.goal else None,
        prerequisites=tuple(target(p) for p in skill.prerequisites),
        lead_ups=tuple(skill.lead_up_exercise_slugs),
    )


def _target_read(progress: analytics.TargetProgress) -> TargetRead:
    return TargetRead(
        exercise_slug=progress.target.exercise,
        reps=progress.target.reps,
        hold_seconds=progress.target.hold_seconds,
        best=progress.best,
        met=progress.met,
    )


@dataclass
class _History:
    sets: list[LoggedSet]
    catalog: dict[str, CatalogExercise]
    weights: list[analytics.BodyWeight]
    tz: ZoneInfo


class ProgressService:
    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def _history(self) -> _History:
        logs = await SetLogRepository(self.session).for_user(self.user.id)
        metrics = await BodyMetricRepository(self.session).for_user(self.user.id)
        profile = await ProfileService(self.session, self.user).get()
        return _History(
            sets=[logged_set(log) for log in logs],
            catalog={e.slug: e for e in await CatalogService(self.session).engine_exercises()},
            weights=body_weights(list(metrics)),
            tz=ZoneInfo(profile.timezone),
        )

    async def summary(self) -> Summary:
        h = await self._history()
        now = datetime.now(UTC)
        today = now.astimezone(h.tz).date()
        week_start = today - timedelta(days=today.weekday())

        workouts = _workouts(h.sets)
        this_week = [
            s
            for s in h.sets
            if analytics.period_start(s.performed_at, Period.WEEK, h.tz) == week_start
        ]
        tonnage = sum(
            (
                t
                for _, t in analytics.tonnage_by_period(
                    this_week, h.catalog, h.weights, Period.WEEK, h.tz
                )
            ),
            Decimal(0),
        )
        return Summary(
            week_streak=analytics.week_streak(workouts.values(), today, h.tz),
            this_week=WeekRead(
                starts_on=week_start,
                workouts=len({s.session_id for s in this_week if not s.is_warmup}),
                tonnage_kg=tonnage,
            ),
            last_workout_at=max(workouts.values(), default=None),
            near_records=[
                NearRecordRead(
                    exercise_slug=n.exercise,
                    record=ResultRead(kind=n.record.kind, value=n.record.value),
                    last=ResultRead(kind=n.last.kind, value=n.last.value),
                    text_ru=n.text_ru,
                )
                for n in analytics.near_records(h.sets, h.catalog, now)
            ],
            imbalances=len(analytics.side_imbalance(h.sets, h.catalog, now)),
        )

    async def pattern(self, code: PatternCode) -> PatternProgress:
        h = await self._history()
        points = analytics.pattern_progress(h.sets, h.catalog, code.value, h.tz)
        return PatternProgress(
            pattern_code=code,
            points=[
                PatternPoint(
                    day=p.day,
                    session_id=p.session_id,
                    exercise_slug=p.exercise,
                    level=p.level,
                    result=_result(p.result),
                )
                for p in points
            ],
        )

    async def exercise(self, slug: str) -> ExerciseProgress:
        h = await self._history()
        exercise = h.catalog.get(slug)
        if exercise is None:
            raise NotFoundException("Такого упражнения нет")

        by_session: dict[str, list[LoggedSet]] = defaultdict(list)
        for s in h.sets:
            if s.exercise == slug and not s.is_warmup:
                by_session[s.session_id].append(s)

        points = []
        for session_id, sets in by_session.items():
            loads = [s.load_kg for s in sets if s.load_kg > 0]
            first = min(s.performed_at for s in sets)
            points.append(
                ExercisePoint(
                    day=first.astimezone(h.tz).date(),
                    session_id=session_id,
                    best=_result(analytics.best_result(sets, exercise)),
                    top_weight_kg=max(loads) if loads else None,
                    working_sets=len({s.set_index for s in sets}),
                    tonnage_kg=sum(
                        (
                            analytics.set_tonnage(
                                s, exercise, analytics.body_mass_at(s.performed_at, h.weights)
                            )
                            for s in sets
                        ),
                        Decimal(0),
                    ),
                )
            )
        points.sort(key=lambda p: (p.day, p.session_id))
        return ExerciseProgress(exercise_slug=slug, points=points)

    async def tonnage(self, query: TonnageQuery) -> list[TonnagePoint]:
        h = await self._history()
        totals = analytics.tonnage_by_period(
            h.sets,
            h.catalog,
            h.weights,
            query.period,
            h.tz,
            patterns={query.pattern.value} if query.pattern else None,
        )
        return [TonnagePoint(starts_on=day, tonnage_kg=kg) for day, kg in totals]

    async def records(self) -> list[PersonalRecordRead]:
        records = await PersonalRecordRepository(self.session).for_user(self.user.id)
        ordered = sorted(records, key=lambda r: r.achieved_at, reverse=True)
        return [PersonalRecordRead.model_validate(r) for r in ordered]

    async def balance(self) -> list[ImbalanceRead]:
        h = await self._history()
        return [
            ImbalanceRead(
                exercise_slug=i.exercise,
                weaker_side=i.weaker_side,
                left_avg=i.left_avg,
                right_avg=i.right_avg,
                gap=i.gap,
                advice_ru=i.advice_ru,
            )
            for i in analytics.side_imbalance(h.sets, h.catalog, datetime.now(UTC))
        ]

    async def skills(self) -> list[SkillProgressRead]:
        """Recomputed from the logs on every read and saved: an achieved skill keeps the
        moment it was first achieved, and never goes back to locked."""
        h = await self._history()
        repo = SkillProgressRepository(self.session)
        stored = {row.skill_slug: row for row in await repo.for_user(self.user.id)}
        result = []
        for skill in await CatalogRepository(self.session).list_skills():
            row = stored.get(skill.slug)
            result.append(await self._skill(skill, row, h, repo))
        await self.session.commit()
        return result

    async def mark_skill(self, slug: str, achieved: bool) -> SkillProgressRead:
        skill = next(
            (s for s in await CatalogRepository(self.session).list_skills() if s.slug == slug),
            None,
        )
        if skill is None:
            raise NotFoundException("Такого навыка нет")
        h = await self._history()
        repo = SkillProgressRepository(self.session)
        row = await repo.get_by(user_id=self.user.id, skill_slug=slug)
        if achieved:
            row = await self._save(row, slug, achieved_at=datetime.now(UTC), repo=repo)
        elif row is not None and row.achieved_at is not None:
            state = analytics.skill_state(_skill(skill), h.sets, h.catalog)
            if state.status is SkillStatus.ACHIEVED:
                raise ValidationFailedException(
                    "Этот навык засчитан по твоим тренировкам — снять отметку нельзя"
                )
            await repo.update(row, achieved_at=None)
        read = await self._skill(skill, row, h, repo)
        await self.session.commit()
        return read

    async def _skill(
        self,
        skill: Skill,
        row: SkillProgress | None,
        h: _History,
        repo: SkillProgressRepository,
    ) -> SkillProgressRead:
        marked = row is not None and row.achieved_at is not None
        state = analytics.skill_state(_skill(skill), h.sets, h.catalog, marked_achieved=marked)
        achieved_at = row.achieved_at if row else None
        if state.status is SkillStatus.ACHIEVED and achieved_at is None:
            achieved_at = _goal_reached_at(_skill(skill), h) or datetime.now(UTC)
        row = await self._save(
            row,
            skill.slug,
            achieved_at=achieved_at,
            repo=repo,
            status=state.status.value,
            current_lead_up_slug=state.current_lead_up,
        )
        return SkillProgressRead(
            skill_slug=skill.slug,
            title_ru=skill.title_ru,
            description_ru=skill.description_ru,
            status=state.status,
            goal=_target_read(state.goal) if state.goal else None,
            prerequisites=[_target_read(p) for p in state.prerequisites],
            lead_up_exercise_slugs=list(skill.lead_up_exercise_slugs),
            current_lead_up_slug=state.current_lead_up,
            achieved_at=row.achieved_at,
        )

    async def _save(
        self,
        row: SkillProgress | None,
        slug: str,
        *,
        achieved_at: datetime | None,
        repo: SkillProgressRepository,
        status: str | None = None,
        current_lead_up_slug: str | None = None,
    ) -> SkillProgress:
        values: dict[str, object] = {"achieved_at": achieved_at}
        if status is not None:
            values["status"] = status
        if current_lead_up_slug is not None:
            values["current_lead_up_slug"] = current_lead_up_slug
        if row is None:
            return await repo.create(user_id=self.user.id, skill_slug=slug, **values)
        return await repo.update(row, **values)


def _workouts(sets: list[LoggedSet]) -> dict[str, datetime]:
    """A workout is a session with at least one working set, dated by its first one."""
    started: dict[str, datetime] = {}
    for s in sets:
        if not s.is_warmup and (
            s.session_id not in started or s.performed_at < started[s.session_id]
        ):
            started[s.session_id] = s.performed_at
    return started


def _goal_reached_at(skill: analytics.Skill, h: _History) -> datetime | None:
    """The moment the logs first met the goal, so the date isn't just "when you looked"."""
    if skill.goal is None:
        return None
    exercise = h.catalog.get(skill.goal.exercise)
    if exercise is None:
        return None
    mine = sorted((s for s in h.sets if s.exercise == exercise.slug), key=lambda s: s.performed_at)
    for i, s in enumerate(mine):
        best = analytics.best_reps(mine[: i + 1], exercise)
        if best is not None and best >= skill.goal.needed:
            return s.performed_at
    return None
