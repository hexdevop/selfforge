import hashlib
import json
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response, status

from app.dependencies.db import DbSession
from app.schemas.catalog import (
    EquipmentRead,
    ExerciseRead,
    ExerciseSummary,
    LadderRead,
    PatternCode,
    PatternRead,
    SkillRead,
)
from app.services.catalog import CatalogService

# Public reference data: no auth, Redis-cached in the service, ETag for clients.
router = APIRouter(tags=["catalog"])


def _etag_response(request: Request, payload: Any) -> Response:
    """Serve JSON with a content hash ETag; answer 304 if the client already has it.

    `no-cache` means "revalidate every time": the browser keeps the body and a
    matching If-None-Match costs one round trip with an empty 304.
    """
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    etag = f'"{hashlib.sha256(body).hexdigest()[:32]}"'
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(body, media_type="application/json", headers=headers)


@router.get("/exercises", response_model=list[ExerciseSummary])
async def list_exercises(
    request: Request,
    session: DbSession,
    pattern: PatternCode | None = None,
    equipment: Annotated[
        str | None,
        Query(description="Equipment code the exercise uses; `none` for bodyweight only"),
    ] = None,
    difficulty_min: Annotated[int | None, Query(ge=1)] = None,
    difficulty_max: Annotated[int | None, Query(ge=1)] = None,
) -> Response:
    payload = await CatalogService(session).list_exercises(
        pattern=pattern,
        equipment=equipment,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
    )
    return _etag_response(request, payload)


@router.get("/exercises/{slug}", response_model=ExerciseRead)
async def get_exercise(slug: str, request: Request, session: DbSession) -> Response:
    return _etag_response(request, await CatalogService(session).get_exercise(slug))


@router.get("/patterns", response_model=list[PatternRead])
async def list_patterns(request: Request, session: DbSession) -> Response:
    return _etag_response(request, await CatalogService(session).list_patterns())


@router.get("/patterns/{code}/ladder", response_model=LadderRead)
async def get_ladder(code: PatternCode, request: Request, session: DbSession) -> Response:
    return _etag_response(request, await CatalogService(session).ladder(code))


@router.get("/equipment", response_model=list[EquipmentRead])
async def list_equipment(request: Request, session: DbSession) -> Response:
    return _etag_response(request, await CatalogService(session).list_equipment())


@router.get("/skills", response_model=list[SkillRead])
async def list_skills(request: Request, session: DbSession) -> Response:
    return _etag_response(request, await CatalogService(session).list_skills())
