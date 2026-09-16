import uuid

from sqlalchemy import select

from app.models.program import PlannedSession, Program, ProgramWeek
from app.repositories.base import BaseRepository


class ProgramRepository(BaseRepository[Program]):
    model = Program

    async def get_by_planned_session(
        self, planned_session_id: uuid.UUID, user_id: uuid.UUID
    ) -> Program | None:
        stmt = (
            select(Program)
            .join(ProgramWeek, ProgramWeek.program_id == Program.id)
            .join(PlannedSession, PlannedSession.program_week_id == ProgramWeek.id)
            .where(PlannedSession.id == planned_session_id, Program.user_id == user_id)
        )
        return (await self.session.scalars(stmt)).first()
