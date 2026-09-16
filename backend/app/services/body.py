import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.engine.analytics import BodyWeight, moving_average
from app.models.body import BodyMetric, ProgressPhoto
from app.models.user import User
from app.repositories.body import BodyMetricRepository, ProgressPhotoRepository
from app.schemas.body import (
    BodyMetricIn,
    BodyMetricRead,
    BodyMetrics,
    PhotoAngle,
    PhotoRead,
    PhotoUpload,
    PhotoUploadRequest,
    TrendPoint,
    UploadForm,
)
from app.services.profile import ProfileService
from app.storage import storage

_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
}


def body_weights(metrics: list[BodyMetric]) -> list[BodyWeight]:
    return [BodyWeight(m.measured_at, m.weight_kg) for m in metrics if m.weight_kg is not None]


class BodyService:
    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user
        self.metrics = BodyMetricRepository(session)
        self.photos = ProgressPhotoRepository(session)

    async def list_metrics(
        self, since: datetime | None = None, until: datetime | None = None
    ) -> BodyMetrics:
        items = list(await self.metrics.for_user(self.user.id, since, until))
        profile = await ProfileService(self.session, self.user).get()
        trend = moving_average(body_weights(items), ZoneInfo(profile.timezone))
        return BodyMetrics(
            items=[BodyMetricRead.model_validate(m) for m in items],
            weight_trend=[TrendPoint(day=day, weight_kg=kg) for day, kg in trend],
        )

    async def add_metric(self, data: BodyMetricIn) -> BodyMetricRead:
        values = data.model_dump(exclude={"measured_at"})
        metric = await self.metrics.create(
            user_id=self.user.id, measured_at=data.measured_at or datetime.now(UTC), **values
        )
        await self.session.commit()
        return BodyMetricRead.model_validate(metric)

    async def delete_metric(self, metric_id: uuid.UUID) -> None:
        metric = await self.metrics.get_by(id=metric_id, user_id=self.user.id)
        if metric is None:
            raise NotFoundException("Такого замера нет")
        await self.metrics.delete(metric)
        await self.session.commit()

    async def list_photos(self) -> list[PhotoRead]:
        return [self._read(p) for p in await self.photos.for_user(self.user.id)]

    async def upload_photo(self, data: PhotoUploadRequest) -> PhotoUpload:
        await storage.ensure_bucket()
        # The key says nothing about the person; the row ties it to them.
        key = f"{uuid.uuid4()}.{_EXTENSIONS[data.content_type]}"
        photo = await self.photos.create(
            user_id=self.user.id,
            taken_at=data.taken_at or datetime.now(UTC),
            storage_key=key,
            angle=data.angle.value,
        )
        await self.session.commit()
        form = storage.upload_form(key, data.content_type)
        return PhotoUpload(
            photo=self._read(photo), upload=UploadForm(url=form["url"], fields=form["fields"])
        )

    async def delete_photo(self, photo_id: uuid.UUID) -> None:
        photo = await self.photos.get_by(id=photo_id, user_id=self.user.id)
        if photo is None:
            raise NotFoundException("Такого фото нет")
        await storage.delete(photo.storage_key)
        await self.photos.delete(photo)
        await self.session.commit()

    def _read(self, photo: ProgressPhoto) -> PhotoRead:
        return PhotoRead(
            id=photo.id,
            taken_at=photo.taken_at,
            angle=PhotoAngle(photo.angle),
            url=storage.view_url(photo.storage_key),
        )
