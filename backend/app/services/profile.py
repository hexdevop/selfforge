from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import OnboardingIncompleteException
from app.engine.assessment import Answers, assess
from app.engine.patterns import main_line, step_at
from app.engine.types import CatalogExercise
from app.models.profile import Profile
from app.models.user import User
from app.repositories.location import LocationRepository
from app.repositories.profile import PatternLevelRepository, ProfileRepository
from app.schemas.catalog import PatternCode
from app.schemas.profile import (
    AssessmentRead,
    AssessmentRequest,
    AssessmentSource,
    DisclaimerRequest,
    GuidanceLevel,
    PatternLevelRead,
    PatternLevelUpdate,
    ProfileUpdate,
)
from app.services.catalog import CatalogService

# The start-up filter recommends a doctor's check from this age (docs/00-product.md).
CLEARANCE_AGE = 60


class ProfileService:
    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user
        self.profiles = ProfileRepository(session)
        self.levels = PatternLevelRepository(session)

    async def get(self) -> Profile:
        profile = await self.profiles.get(self.user.id)
        if profile is None:
            profile = await self.profiles.create(user_id=self.user.id, health_flags=[])
            await self.session.commit()
        return profile

    async def update(self, data: ProfileUpdate) -> Profile:
        profile = await self.get()
        await self.profiles.update(profile, **data.model_dump(exclude_unset=True))
        await self.session.commit()
        return profile

    async def accept_disclaimer(self, data: DisclaimerRequest) -> Profile:
        profile = await self.get()
        age = datetime.now(UTC).year - data.birth_year
        await self.profiles.update(
            profile,
            birth_year=data.birth_year,
            health_flags=list(data.health_flags),
            needs_medical_clearance=(
                data.heart_condition or data.pregnancy or data.recent_injury or age >= CLEARANCE_AGE
            ),
            medical_disclaimer_accepted_at=datetime.now(UTC),
        )
        await self.session.commit()
        return profile

    async def assess(self, data: AssessmentRequest) -> AssessmentRead:
        answers = Answers(
            data.pushups, data.pullups, data.squats, data.pistol, data.experienced, data.knows_terms
        )
        result = assess(answers, data.shift)
        await self._save_levels(result.levels, AssessmentSource.ONBOARDING)

        profile = await self.get()
        await self.profiles.update(profile, guidance_level=result.guidance_level)
        await self.session.commit()
        return AssessmentRead(
            overall=result.overall,
            guidance_level=GuidanceLevel(result.guidance_level),
            levels=await self.list_levels(),
        )

    async def list_levels(self) -> list[PatternLevelRead]:
        rows = await self.levels.list_for_user(self.user.id)
        order = list(PatternCode)
        return sorted(
            (PatternLevelRead.model_validate(r) for r in rows),
            key=lambda level: order.index(level.pattern_code),
        )

    async def update_levels(self, items: list[PatternLevelUpdate]) -> list[PatternLevelRead]:
        await self._save_levels(
            {item.pattern_code.value: item.estimated_level for item in items},
            AssessmentSource.MANUAL,
        )
        await self.session.commit()
        return await self.list_levels()

    async def complete_onboarding(self) -> Profile:
        profile = await self.get()
        missing = {
            "disclaimer": profile.medical_disclaimer_accepted_at is None,
            "assessment": not await self.levels.list_for_user(self.user.id),
            "goal_primary": profile.goal_primary is None,
            "days_per_week": profile.days_per_week is None,
            "session_minutes": profile.session_minutes is None,
            "locations": not await LocationRepository(self.session).list_for_user(self.user.id),
        }
        if any(missing.values()):
            raise OnboardingIncompleteException(
                fields={step: "Не заполнено" for step, is_missing in missing.items() if is_missing}
            )
        if profile.onboarding_completed_at is None:
            await self.profiles.update(profile, onboarding_completed_at=datetime.now(UTC))
            await self.session.commit()
        return profile

    async def _save_levels(self, levels: dict[str, int], source: AssessmentSource) -> None:
        """Each level lands on the hardest main-line step not above it."""
        by_pattern: dict[str, list[CatalogExercise]] = defaultdict(list)
        for exercise in await CatalogService(self.session).engine_exercises():
            by_pattern[exercise.pattern].append(exercise)

        rows = []
        for pattern, level in levels.items():
            step = step_at(main_line(by_pattern[pattern]), level)
            rows.append(
                {
                    "pattern_code": pattern,
                    "estimated_level": step.level,
                    "current_exercise_slug": step.slug,
                    "assessment_source": source.value,
                }
            )
        await self.levels.upsert(self.user.id, rows)
