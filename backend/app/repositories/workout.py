import uuid
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models.workout import PersonalRecord, SetLog, WorkoutSession
from app.repositories.base import BaseRepository
from app.schemas.pagination import Page, PageParams


class WorkoutSessionRepository(BaseRepository[WorkoutSession]):
    model = WorkoutSession

    async def get_for_user(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkoutSession | None:
        stmt = select(WorkoutSession).where(
            WorkoutSession.id == session_id, WorkoutSession.user_id == user_id
        )
        return (await self.session.scalars(stmt)).first()

    async def in_progress(self, user_id: uuid.UUID) -> WorkoutSession | None:
        stmt = select(WorkoutSession).where(
            WorkoutSession.user_id == user_id, WorkoutSession.status == "in_progress"
        )
        return (await self.session.scalars(stmt)).first()

    async def history(
        self, user_id: uuid.UUID, pagination: PageParams, status: str | None = None
    ) -> Page[WorkoutSession]:
        filters: dict[str, Any] = {"user_id": user_id}
        if status is not None:
            filters["status"] = status
        return await self.list(filters, pagination, order_by=WorkoutSession.started_at.desc())

    async def all_for_user(self, user_id: uuid.UUID) -> Sequence[WorkoutSession]:
        stmt = (
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user_id)
            .order_by(WorkoutSession.started_at)
        )
        return (await self.session.scalars(stmt)).all()

    async def completed_planned_ids(self, planned_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        ids = list(planned_ids)
        if not ids:
            return set()
        stmt = select(WorkoutSession.planned_session_id).where(
            WorkoutSession.planned_session_id.in_(ids), WorkoutSession.status == "completed"
        )
        return {row for row in await self.session.scalars(stmt) if row is not None}


class SetLogRepository(BaseRepository[SetLog]):
    model = SetLog

    async def add_batch(self, rows: Sequence[dict[str, Any]]) -> list[SetLog]:
        """Store what isn't stored yet and return the rows that landed now.

        The client keeps a buffer and retries it, so the same `client_uuid` arrives more
        than once; a repeat is a no-op, not an error.
        """
        if not rows:
            return []
        stmt = (
            insert(SetLog)
            .values(list(rows))
            .on_conflict_do_nothing(constraint="uq_set_logs_client_uuid")
            .returning(SetLog)
        )
        return list((await self.session.scalars(stmt)).all())

    async def for_session(self, session_id: uuid.UUID) -> Sequence[SetLog]:
        stmt = (
            select(SetLog)
            .where(SetLog.session_id == session_id)
            .order_by(SetLog.performed_at, SetLog.set_index)
        )
        return (await self.session.scalars(stmt)).all()

    async def for_user(self, user_id: uuid.UUID) -> Sequence[SetLog]:
        """The whole history of one person, oldest first — what analytics reads."""
        stmt = select(SetLog).where(SetLog.user_id == user_id).order_by(SetLog.performed_at)
        return (await self.session.scalars(stmt)).all()

    async def for_sessions(self, session_ids: Sequence[uuid.UUID]) -> Sequence[SetLog]:
        if not session_ids:
            return []
        stmt = (
            select(SetLog)
            .where(SetLog.session_id.in_(session_ids))
            .order_by(SetLog.performed_at, SetLog.set_index)
        )
        return (await self.session.scalars(stmt)).all()


class PersonalRecordRepository(BaseRepository[PersonalRecord]):
    model = PersonalRecord

    async def for_user(self, user_id: uuid.UUID) -> Sequence[PersonalRecord]:
        stmt = select(PersonalRecord).where(PersonalRecord.user_id == user_id)
        return (await self.session.scalars(stmt)).all()
