import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.dependencies.auth import CurrentActiveUser
from app.dependencies.db import DbSession
from app.schemas.body import (
    BodyMetricIn,
    BodyMetricRead,
    BodyMetrics,
    PhotoRead,
    PhotoUpload,
    PhotoUploadRequest,
)
from app.services.body import BodyService

router = APIRouter(prefix="/body", tags=["body"])


@router.get("/metrics", response_model=BodyMetrics)
async def list_metrics(
    user: CurrentActiveUser,
    session: DbSession,
    since: Annotated[datetime | None, Query(alias="from")] = None,
    until: Annotated[datetime | None, Query(alias="to")] = None,
) -> BodyMetrics:
    return await BodyService(session, user).list_metrics(since, until)


@router.post("/metrics", response_model=BodyMetricRead, status_code=status.HTTP_201_CREATED)
async def add_metric(
    data: BodyMetricIn, user: CurrentActiveUser, session: DbSession
) -> BodyMetricRead:
    return await BodyService(session, user).add_metric(data)


@router.delete("/metrics/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_metric(metric_id: uuid.UUID, user: CurrentActiveUser, session: DbSession) -> None:
    await BodyService(session, user).delete_metric(metric_id)


@router.get("/photos", response_model=list[PhotoRead])
async def list_photos(user: CurrentActiveUser, session: DbSession) -> list[PhotoRead]:
    return await BodyService(session, user).list_photos()


@router.post("/photos/upload-url", response_model=PhotoUpload, status_code=status.HTTP_201_CREATED)
async def photo_upload_url(
    data: PhotoUploadRequest, user: CurrentActiveUser, session: DbSession
) -> PhotoUpload:
    """The file goes straight to storage with the returned form, never through the API."""
    return await BodyService(session, user).upload_photo(data)


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(photo_id: uuid.UUID, user: CurrentActiveUser, session: DbSession) -> None:
    await BodyService(session, user).delete_photo(photo_id)
