import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    NotFoundException,
    OnboardingIncompleteException,
    ValidationFailedException,
)
from app.engine import mesocycle
from app.engine.goals import Goal
from app.models.location import Location
from app.models.profile import Profile
from app.models.program import PlannedSession, Program, ProgramWeek
from app.models.user import User
from app.repositories.catalog import CatalogRepository
from app.repositories.location import LocationRepository
from app.repositories.profile import PatternLevelRepository
from app.repositories.program import ProgramRepository
from app.repositories.workout import WorkoutSessionRepository
from app.schemas.program import ProgramDraft, ProgramRead, ProgramRequest, ProgramStatus
from app.services.catalog import CatalogService
from app.services.location import to_engine_location
from app.services.profile import ProfileService


def _block(block: mesocycle.Block) -> dict[str, object]:
    return {
        "kind": block.kind.value,
        "minutes": block.minutes,
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
                "tempo": e.tempo,
            }
            for e in block.exercises
        ],
    }


def _program_input(
    profile: Profile, levels: dict[str, int], day_locations: list[str]
) -> mesocycle.ProgramInput:
    if profile.goal_primary is None:
        raise OnboardingIncompleteException("Сначала пройди онбординг до конца")
    return mesocycle.ProgramInput(
        goal=Goal(profile.goal_primary),
        secondary_goal=Goal(profile.goal_secondary) if profile.goal_secondary else None,
        # A profile finishes onboarding only with these set; the fallback is for type safety.
        session_minutes=profile.session_minutes or 45,
        levels=levels,
        day_locations=tuple(day_locations),
        health_flags=frozenset(profile.health_flags),
        needs_medical_clearance=profile.needs_medical_clearance,
    )


class ProgramService:
    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user
        self.programs = ProgramRepository(session)

    async def preview(self, data: ProgramRequest) -> ProgramDraft:
        # The same rows `create` would save, just never added to the session.
        return ProgramDraft.model_validate(await self._generate(data))

    async def create(self, data: ProgramRequest) -> ProgramRead:
        """Start a new program; the one running so far is abandoned."""
        program = await self._generate(data)
        if (active := await self._active()) is not None:
            await self.programs.update(active, status=ProgramStatus.ABANDONED.value)
        self.session.add(program)
        await self.session.commit()
        return await self.get(program.id)

    async def active(self) -> ProgramRead:
        program = await self._active()
        if program is None:
            raise NotFoundException("Программы пока нет — собери её")
        return ProgramRead.model_validate(program)

    async def get(self, program_id: uuid.UUID) -> ProgramRead:
        program = await self.programs.get_by(id=program_id, user_id=self.user.id)
        if program is None:
            raise NotFoundException("Такой программы нет")
        return ProgramRead.model_validate(program)

    async def planned_session(self, planned_session_id: uuid.UUID) -> PlannedSession:
        """A day of one of this person's own programs."""
        program = await self.programs.get_by_planned_session(planned_session_id, self.user.id)
        if program is None:
            raise NotFoundException("Такого дня в программе нет")
        return next(
            day for week in program.weeks for day in week.sessions if day.id == planned_session_id
        )

    async def next_planned_session(self) -> PlannedSession:
        """The first day of the active program that has no completed workout yet.

        Days are ordinal, not tied to weekdays: a missed day is simply the next one up.
        """
        program = await self._active()
        if program is None:
            raise ValidationFailedException("Сначала собери программу")
        days = [day for week in program.weeks for day in week.sessions]
        if not days:
            raise NotFoundException("В программе нет ни одного дня")
        done = await WorkoutSessionRepository(self.session).completed_planned_ids(
            day.id for day in days
        )
        return next((day for day in days if day.id not in done), days[-1])

    async def one_off_day(self, location: Location) -> mesocycle.PlannedDay:
        """A full-body day at `location` for a workout outside the program."""
        profile = await ProfileService(self.session, self.user).get()
        if profile.onboarding_completed_at is None or not profile.goal_primary:
            raise OnboardingIncompleteException("Сначала пройди онбординг до конца")
        return mesocycle.build_one_off_day(
            _program_input(profile, await self._levels(), [str(location.id)]),
            to_engine_location(location),
            await CatalogService(self.session).engine_exercises(),
        )

    async def _levels(self) -> dict[str, int]:
        return {
            level.pattern_code: level.estimated_level
            for level in await PatternLevelRepository(self.session).list_for_user(self.user.id)
        }

    async def _active(self) -> Program | None:
        return await self.programs.get_by(user_id=self.user.id, status=ProgramStatus.ACTIVE.value)

    async def _generate(self, data: ProgramRequest) -> Program:
        profile = await ProfileService(self.session, self.user).get()
        goal, days, minutes = profile.goal_primary, profile.days_per_week, profile.session_minutes
        if profile.onboarding_completed_at is None or not (goal and days and minutes):
            raise OnboardingIncompleteException("Сначала пройди онбординг до конца")

        # The default place is listed first.
        locations = {
            str(loc.id): loc
            for loc in await LocationRepository(self.session).list_for_user(self.user.id)
        }
        if data.day_locations is not None:
            day_locations = [str(loc_id) for loc_id in data.day_locations]
        else:
            day_locations = [next(iter(locations))] * days if locations else []
        if not locations:
            raise ValidationFailedException(
                "Добавь хотя бы одно место для тренировок", {"day_locations": "Нет ни одного места"}
            )
        if len(day_locations) != days:
            raise ValidationFailedException(
                fields={"day_locations": f"Нужно место для каждого из {days} дней"}
            )
        if any(loc_id not in locations for loc_id in day_locations):
            raise ValidationFailedException(fields={"day_locations": "Такого места нет"})

        levels = await self._levels()
        used = {loc_id: locations[loc_id] for loc_id in dict.fromkeys(day_locations)}
        titles = {
            e.code: e.title_ru for e in await CatalogRepository(self.session).list_equipment()
        }
        program = mesocycle.build_mesocycle(
            _program_input(profile, levels, day_locations),
            {loc_id: to_engine_location(loc) for loc_id, loc in used.items()},
            await CatalogService(self.session).engine_exercises(),
            titles,
        )

        snapshot = {
            "profile": {
                "goal_primary": goal,
                "goal_secondary": profile.goal_secondary,
                "days_per_week": days,
                "session_minutes": minutes,
                "health_flags": profile.health_flags,
                "needs_medical_clearance": profile.needs_medical_clearance,
            },
            "levels": levels,
            "day_locations": day_locations,
            "locations": [
                {
                    "id": loc_id,
                    "kind": loc.kind,
                    "title": loc.title,
                    "constraints": loc.constraints,
                    "equipment": [
                        {"code": e.equipment_code, "quantity": e.quantity, "details": e.details}
                        for e in loc.equipment
                    ],
                }
                for loc_id, loc in used.items()
            ],
        }
        return Program(
            user_id=self.user.id,
            goal_primary=program.goal.value,
            structure=program.structure.value,
            weeks_total=len(program.weeks),
            started_at=datetime.now(UTC),
            status=ProgramStatus.ACTIVE.value,
            generation_input=snapshot,
            rationale_ru=program.rationale_ru,
            weeks=[
                ProgramWeek(
                    index=week.index,
                    kind=week.kind.value,
                    volume_multiplier=week.volume_multiplier,
                    sessions=[
                        PlannedSession(
                            day_index=day.day_index,
                            location_id=uuid.UUID(day.location_id),
                            title_ru=day.title,
                            focus=list(day.focus),
                            estimated_minutes=day.minutes,
                            blocks=[_block(b) for b in day.blocks],
                        )
                        for day in week.days
                    ],
                )
                for week in program.weeks
            ],
        )
