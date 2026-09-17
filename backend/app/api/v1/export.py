from datetime import UTC, datetime

from fastapi import APIRouter, Response

from app.dependencies.auth import CurrentActiveUser
from app.dependencies.db import DbSession
from app.schemas.export import Export
from app.services.export import ExportService

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/all", response_model=Export)
async def export_all(user: CurrentActiveUser, session: DbSession, response: Response) -> Export:
    """A full dump of the person's data as a JSON file download."""
    day = datetime.now(UTC).date().isoformat()
    response.headers["Content-Disposition"] = f'attachment; filename="selfforge-{day}.json"'
    return await ExportService(session, user).everything()
