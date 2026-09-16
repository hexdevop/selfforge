import uuid

from fastapi import APIRouter, status

from app.dependencies.auth import CurrentActiveUser
from app.dependencies.db import DbSession
from app.dependencies.pagination import Pagination
from app.schemas.pagination import Page
from app.schemas.workout import (
    SessionFinish,
    SessionStart,
    SetsAccepted,
    SetsBatch,
    SubstituteRequest,
    TrimRequest,
    WorkoutSessionRead,
)
from app.services.workout import WorkoutService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=WorkoutSessionRead, status_code=status.HTTP_201_CREATED)
async def start_session(
    data: SessionStart, user: CurrentActiveUser, session: DbSession
) -> WorkoutSessionRead:
    """Prepare today's workout: weights from history, readiness applied, warm-up added."""
    return await WorkoutService(session, user).start(data)


@router.get("", response_model=Page[WorkoutSessionRead])
async def list_sessions(
    user: CurrentActiveUser, session: DbSession, pagination: Pagination
) -> Page[WorkoutSessionRead]:
    return await WorkoutService(session, user).history(pagination)


@router.get("/{session_id}", response_model=WorkoutSessionRead)
async def get_session(
    session_id: uuid.UUID, user: CurrentActiveUser, session: DbSession
) -> WorkoutSessionRead:
    return await WorkoutService(session, user).get(session_id)


@router.post("/{session_id}/sets", response_model=SetsAccepted)
async def log_sets(
    session_id: uuid.UUID, batch: SetsBatch, user: CurrentActiveUser, session: DbSession
) -> SetsAccepted:
    """The buffer the client keeps, sent in one go. Repeating a `client_uuid` is a no-op."""
    return await WorkoutService(session, user).log_sets(session_id, batch)


@router.post("/{session_id}/substitute", response_model=WorkoutSessionRead)
async def substitute(
    session_id: uuid.UUID,
    data: SubstituteRequest,
    user: CurrentActiveUser,
    session: DbSession,
) -> WorkoutSessionRead:
    return await WorkoutService(session, user).substitute(session_id, data)


@router.post("/{session_id}/trim", response_model=WorkoutSessionRead)
async def trim(
    session_id: uuid.UUID, data: TrimRequest, user: CurrentActiveUser, session: DbSession
) -> WorkoutSessionRead:
    """Rebuild what's left of the session for the time that's actually available."""
    return await WorkoutService(session, user).trim(session_id, data)


@router.post("/{session_id}/finish", response_model=WorkoutSessionRead)
async def finish(
    session_id: uuid.UUID, data: SessionFinish, user: CurrentActiveUser, session: DbSession
) -> WorkoutSessionRead:
    return await WorkoutService(session, user).finish(session_id, data)


@router.post("/{session_id}/abort", response_model=WorkoutSessionRead)
async def abort(
    session_id: uuid.UUID, user: CurrentActiveUser, session: DbSession
) -> WorkoutSessionRead:
    return await WorkoutService(session, user).abort(session_id)
