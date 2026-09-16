from typing import Any

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    body,
    catalog,
    locations,
    profile,
    programs,
    progress,
    sessions,
    users,
    weather,
)
from app.schemas.error import ErrorResponse

# Every error goes through the handlers in `app.main`, so document that single
# shape for the whole API (it also replaces FastAPI's default 422 schema).
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    "4XX": {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}

router = APIRouter(responses=_ERROR_RESPONSES)
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(catalog.router)
router.include_router(profile.router)
router.include_router(locations.router)
router.include_router(programs.router)
router.include_router(sessions.router)
router.include_router(body.router)
router.include_router(progress.router)
router.include_router(weather.router)
