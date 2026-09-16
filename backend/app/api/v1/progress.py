from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencies.auth import CurrentActiveUser
from app.dependencies.db import DbSession
from app.schemas.catalog import PatternCode
from app.schemas.progress import (
    ExerciseProgress,
    ImbalanceRead,
    PatternProgress,
    SkillMark,
    SkillProgressRead,
    Summary,
    TonnagePoint,
    TonnageQuery,
)
from app.schemas.workout import PersonalRecordRead
from app.services.progress import ProgressService

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/summary", response_model=Summary)
async def summary(user: CurrentActiveUser, session: DbSession) -> Summary:
    """Week streak, this week's volume and records within reach."""
    return await ProgressService(session, user).summary()


@router.get("/patterns/{code}", response_model=PatternProgress)
async def pattern(
    code: PatternCode, user: CurrentActiveUser, session: DbSession
) -> PatternProgress:
    """One point per workout: the hardest step of the ladder done and its best set."""
    return await ProgressService(session, user).pattern(code)


@router.get("/exercises/{slug}", response_model=ExerciseProgress)
async def exercise(slug: str, user: CurrentActiveUser, session: DbSession) -> ExerciseProgress:
    return await ProgressService(session, user).exercise(slug)


@router.get("/tonnage", response_model=list[TonnagePoint])
async def tonnage(
    query: Annotated[TonnageQuery, Query()], user: CurrentActiveUser, session: DbSession
) -> list[TonnagePoint]:
    return await ProgressService(session, user).tonnage(query)


@router.get("/records", response_model=list[PersonalRecordRead])
async def records(user: CurrentActiveUser, session: DbSession) -> list[PersonalRecordRead]:
    return await ProgressService(session, user).records()


@router.get("/balance", response_model=list[ImbalanceRead])
async def balance(user: CurrentActiveUser, session: DbSession) -> list[ImbalanceRead]:
    """One-sided exercises where one side lags over 15% on average across four weeks."""
    return await ProgressService(session, user).balance()


@router.get("/skills", response_model=list[SkillProgressRead])
async def skills(user: CurrentActiveUser, session: DbSession) -> list[SkillProgressRead]:
    return await ProgressService(session, user).skills()


@router.put("/skills/{slug}", response_model=SkillProgressRead)
async def mark_skill(
    slug: str, data: SkillMark, user: CurrentActiveUser, session: DbSession
) -> SkillProgressRead:
    """Mark a skill achieved by hand — for skills the catalog has no exercise to check."""
    return await ProgressService(session, user).mark_skill(slug, data.achieved)
