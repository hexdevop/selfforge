import uuid

from fastapi import APIRouter, status

from app.dependencies.auth import CurrentActiveUser
from app.dependencies.db import DbSession
from app.schemas.program import PlannedSessionRead, ProgramDraft, ProgramRead, ProgramRequest
from app.services.program import ProgramService

router = APIRouter(prefix="/programs", tags=["programs"])


@router.post("/preview", response_model=ProgramDraft)
async def preview_program(
    data: ProgramRequest, user: CurrentActiveUser, session: DbSession
) -> ProgramDraft:
    """Build a program without saving it, for the «here's what you'd get» screen."""
    return await ProgramService(session, user).preview(data)


@router.post("", response_model=ProgramRead, status_code=status.HTTP_201_CREATED)
async def create_program(
    data: ProgramRequest, user: CurrentActiveUser, session: DbSession
) -> ProgramRead:
    return await ProgramService(session, user).create(data)


@router.get("/active", response_model=ProgramRead)
async def active_program(user: CurrentActiveUser, session: DbSession) -> ProgramRead:
    return await ProgramService(session, user).active()


@router.get("/active/next-session", response_model=PlannedSessionRead)
async def next_session(user: CurrentActiveUser, session: DbSession) -> PlannedSessionRead:
    """The day to train next: the first one of the active program without a finished workout."""
    return PlannedSessionRead.model_validate(
        await ProgramService(session, user).next_planned_session()
    )


@router.get("/{program_id}", response_model=ProgramRead)
async def get_program(
    program_id: uuid.UUID, user: CurrentActiveUser, session: DbSession
) -> ProgramRead:
    return await ProgramService(session, user).get(program_id)
