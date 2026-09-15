from fastapi import APIRouter

from app.dependencies.auth import CurrentActiveUser
from app.dependencies.db import DbSession
from app.schemas.profile import (
    AssessmentRead,
    AssessmentRequest,
    DisclaimerRequest,
    PatternLevelRead,
    PatternLevelUpdate,
    ProfileRead,
    ProfileUpdate,
)
from app.services.profile import ProfileService

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileRead)
async def get_profile(user: CurrentActiveUser, session: DbSession) -> ProfileRead:
    return ProfileRead.model_validate(await ProfileService(session, user).get())


@router.patch("", response_model=ProfileRead)
async def update_profile(
    data: ProfileUpdate, user: CurrentActiveUser, session: DbSession
) -> ProfileRead:
    return ProfileRead.model_validate(await ProfileService(session, user).update(data))


@router.post("/disclaimer", response_model=ProfileRead)
async def accept_disclaimer(
    data: DisclaimerRequest, user: CurrentActiveUser, session: DbSession
) -> ProfileRead:
    return ProfileRead.model_validate(await ProfileService(session, user).accept_disclaimer(data))


@router.post("/assessment", response_model=AssessmentRead)
async def assess(
    data: AssessmentRequest, user: CurrentActiveUser, session: DbSession
) -> AssessmentRead:
    return await ProfileService(session, user).assess(data)


@router.get("/pattern-levels", response_model=list[PatternLevelRead])
async def list_pattern_levels(
    user: CurrentActiveUser, session: DbSession
) -> list[PatternLevelRead]:
    return await ProfileService(session, user).list_levels()


@router.patch("/pattern-levels", response_model=list[PatternLevelRead])
async def update_pattern_levels(
    items: list[PatternLevelUpdate], user: CurrentActiveUser, session: DbSession
) -> list[PatternLevelRead]:
    return await ProfileService(session, user).update_levels(items)


@router.post("/onboarding/complete", response_model=ProfileRead)
async def complete_onboarding(user: CurrentActiveUser, session: DbSession) -> ProfileRead:
    return ProfileRead.model_validate(await ProfileService(session, user).complete_onboarding())
