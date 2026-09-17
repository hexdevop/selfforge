from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.body import SkillProgressRepository
from app.repositories.program import ProgramRepository
from app.repositories.workout import PersonalRecordRepository, WorkoutSessionRepository
from app.schemas.body import BodyMetricRead
from app.schemas.export import Export, SkillProgressExport
from app.schemas.profile import ProfileRead
from app.schemas.program import ProgramRead
from app.schemas.user import UserRead
from app.schemas.workout import PersonalRecordRead
from app.services.body import BodyService
from app.services.location import LocationService
from app.services.profile import ProfileService
from app.services.workout import WorkoutService


class ExportService:
    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def everything(self) -> Export:
        body = BodyService(self.session, self.user)
        workouts = WorkoutService(self.session, self.user)
        sessions = await WorkoutSessionRepository(self.session).all_for_user(self.user.id)
        records = await PersonalRecordRepository(self.session).for_user(self.user.id)
        return Export(
            exported_at=datetime.now(UTC),
            user=UserRead.model_validate(self.user),
            profile=ProfileRead.model_validate(await ProfileService(self.session, self.user).get()),
            pattern_levels=await ProfileService(self.session, self.user).list_levels(),
            locations=await LocationService(self.session, self.user).list_all(),
            programs=[
                ProgramRead.model_validate(p)
                for p in await ProgramRepository(self.session).all_for_user(self.user.id)
            ],
            workouts=[await workouts.read(w) for w in sessions],
            personal_records=[
                PersonalRecordRead.model_validate(r)
                for r in sorted(records, key=lambda r: r.achieved_at)
            ],
            body_metrics=[
                BodyMetricRead.model_validate(m)
                for m in reversed((await body.list_metrics()).items)
            ],
            photos=list(reversed(await body.list_photos())),
            skill_progress=[
                SkillProgressExport.model_validate(row)
                for row in await SkillProgressRepository(self.session).for_user(self.user.id)
            ],
        )
