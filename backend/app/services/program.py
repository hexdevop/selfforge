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
from app.models.program import PlannedSession, Program, ProgramWeek
from app.models.user import User
from app.repositories.catalog import CatalogRepository
from app.repositories.location import LocationRepository
from app.repositories.profile import PatternLevelRepository
from app.repositories.program import ProgramRepository
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

        levels = {
            level.pattern_code: level.estimated_level
            for level in await PatternLevelRepository(self.session).list_for_user(self.user.id)
        }
        used = {loc_id: locations[loc_id] for loc_id in dict.fromkeys(day_locations)}
        titles = {
            e.code: e.title_ru for e in await CatalogRepository(self.session).list_equipment()
        }
        program = mesocycle.build_mesocycle(
            mesocycle.ProgramInput(
                goal=Goal(goal),
                secondary_goal=Goal(profile.goal_secondary) if profile.goal_secondary else None,
                session_minutes=minutes,
                levels=levels,
                day_locations=tuple(day_locations),
                health_flags=frozenset(profile.health_flags),
                needs_medical_clearance=profile.needs_medical_clearance,
            ),
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
