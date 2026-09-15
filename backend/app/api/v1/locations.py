import uuid

from fastapi import APIRouter, status

from app.dependencies.auth import CurrentActiveUser
from app.dependencies.db import DbSession
from app.schemas.location import (
    LocationCreate,
    LocationEquipmentIn,
    LocationRead,
    LocationUpdate,
    PlatesRead,
    PlatesRequest,
    WeightGrid,
)
from app.services.location import LocationService

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=list[LocationRead])
async def list_locations(user: CurrentActiveUser, session: DbSession) -> list[LocationRead]:
    return await LocationService(session, user).list_all()


@router.post("", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
async def create_location(
    data: LocationCreate, user: CurrentActiveUser, session: DbSession
) -> LocationRead:
    return await LocationService(session, user).create(data)


@router.patch("/{location_id}", response_model=LocationRead)
async def update_location(
    location_id: uuid.UUID, data: LocationUpdate, user: CurrentActiveUser, session: DbSession
) -> LocationRead:
    return await LocationService(session, user).update(location_id, data)


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: uuid.UUID, user: CurrentActiveUser, session: DbSession
) -> None:
    await LocationService(session, user).delete(location_id)


@router.put("/{location_id}/equipment", response_model=LocationRead)
async def replace_equipment(
    location_id: uuid.UUID,
    items: list[LocationEquipmentIn],
    user: CurrentActiveUser,
    session: DbSession,
) -> LocationRead:
    return await LocationService(session, user).replace_equipment(location_id, items)


@router.get("/{location_id}/weight-grid", response_model=list[WeightGrid])
async def weight_grid(
    location_id: uuid.UUID, user: CurrentActiveUser, session: DbSession
) -> list[WeightGrid]:
    return await LocationService(session, user).weight_grids(location_id)


@router.post("/{location_id}/plates", response_model=PlatesRead)
async def plates(
    location_id: uuid.UUID, data: PlatesRequest, user: CurrentActiveUser, session: DbSession
) -> PlatesRead:
    return await LocationService(session, user).plates(location_id, data)
