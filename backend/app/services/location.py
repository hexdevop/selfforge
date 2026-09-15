import uuid
from bisect import bisect_left

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationFailedException
from app.engine import types as engine
from app.engine.inventory import is_available, min_step, plate_breakdown, weight_grid
from app.models.catalog import EquipmentItem
from app.models.location import Location, LocationEquipment
from app.models.user import User
from app.repositories.catalog import CatalogRepository
from app.repositories.location import LocationRepository
from app.schemas.catalog import ExerciseSummary
from app.schemas.location import (
    Constraints,
    EquipmentDetails,
    LocationCreate,
    LocationEquipmentIn,
    LocationRead,
    LocationUpdate,
    PlateSet,
    PlatesRead,
    PlatesRequest,
    WeightGrid,
)
from app.services.catalog import to_engine_exercise
from app.services.profile import ProfileService

WEIGHTED = ("barbell", "dumbbell", "kettlebell")


def to_engine_location(location: Location) -> engine.Location:
    equipment = {}
    for item in location.equipment:
        details = EquipmentDetails.model_validate(item.details)
        adjustable = details.bar_kg is not None
        equipment[item.equipment_code] = engine.Equipment(
            code=item.equipment_code,
            quantity=item.quantity,
            bar_kg=details.bar_kg if adjustable else None,
            plates=tuple(engine.Plate(p.kg, p.count) for p in details.plates),
            weights_kg=() if adjustable else tuple(details.weights_kg),
        )
    c = Constraints.model_validate(location.constraints)
    return engine.Location(
        id=str(location.id),
        equipment=equipment,
        constraints=engine.Constraints(c.quiet_mode, c.low_ceiling, c.limited_space, c.surface),
        kind=location.kind,
        title=location.title,
    )


def _details_problem(item: LocationEquipmentIn, catalog_item: EquipmentItem) -> str | None:
    d = item.details
    if item.quantity > 1 and not catalog_item.supports_quantity:
        return "Это оборудование не бывает парой"
    if item.equipment_code == "barbell" and (d.bar_kg is None or not d.plates):
        return "Укажи вес грифа и блины"
    if item.equipment_code == "kettlebell" and not d.weights_kg:
        return "Укажи вес каждой гири"
    if item.equipment_code == "dumbbell":
        if d.type is None:
            return "Выбери: разборные или фиксированные"
        if d.type == "fixed" and not d.weights_kg:
            return "Укажи веса гантелей"
        if d.type == "adjustable" and (d.bar_kg is None or not d.plates):
            return "Укажи вес грифа и блины"
    return None


class LocationService:
    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user
        self.locations = LocationRepository(session)
        self.catalog = CatalogRepository(session)

    async def list_all(self) -> list[LocationRead]:
        return await self._read(*await self.locations.list_for_user(self.user.id))

    async def create(self, data: LocationCreate) -> LocationRead:
        is_first = not await self.locations.list_for_user(self.user.id)
        if data.is_default:
            await self.locations.clear_default(self.user.id)
        location = await self.locations.create(
            user_id=self.user.id,
            kind=data.kind.value,
            title=data.title,
            is_default=data.is_default or is_first,
            travel_minutes=data.travel_minutes,
            constraints=data.constraints.model_dump(mode="json"),
            equipment=[],
        )
        await self.session.commit()
        return (await self._read(location))[0]

    async def update(self, location_id: uuid.UUID, data: LocationUpdate) -> LocationRead:
        location = await self._get(location_id)
        values = data.model_dump(exclude_unset=True, mode="json")
        if values.get("is_default"):
            await self.locations.clear_default(self.user.id)
        await self.locations.update(location, **values)
        await self.session.commit()
        await self.session.refresh(location)
        return (await self._read(location))[0]

    async def delete(self, location_id: uuid.UUID) -> None:
        await self.locations.delete(await self._get(location_id))
        await self.session.commit()

    async def replace_equipment(
        self, location_id: uuid.UUID, items: list[LocationEquipmentIn]
    ) -> LocationRead:
        location = await self._get(location_id)
        known = {e.code: e for e in await self.catalog.list_equipment()}

        problems: dict[str, str] = {}
        seen: set[str] = set()
        for item in items:
            code = item.equipment_code
            catalog_item = known.get(code)
            if catalog_item is None:
                problems[code] = "Такого оборудования нет в справочнике"
            elif code in seen:
                problems[code] = "Указано дважды"
            elif problem := _details_problem(item, catalog_item):
                problems[code] = problem
            seen.add(code)
        if problems:
            raise ValidationFailedException(fields=problems)

        # Delete first: the (location, code) pair is unique and the ORM would insert first.
        location.equipment.clear()
        await self.session.flush()
        location.equipment.extend(
            LocationEquipment(
                equipment_code=item.equipment_code,
                quantity=item.quantity,
                details=item.details.model_dump(mode="json", exclude_defaults=True),
            )
            for item in items
        )
        await self.session.commit()
        await self.session.refresh(location)
        return (await self._read(location))[0]

    async def available_exercises(self, location_id: uuid.UUID) -> list[ExerciseSummary]:
        location = to_engine_location(await self._get(location_id))
        health = (await ProfileService(self.session, self.user).get()).health_flags
        return [
            ExerciseSummary.model_validate(e)
            for e in await self.catalog.list_exercises()
            if is_available(to_engine_exercise(e), location, health)
        ]

    async def weight_grids(self, location_id: uuid.UUID) -> list[WeightGrid]:
        location = to_engine_location(await self._get(location_id))
        grids = []
        for code in WEIGHTED:
            if (equipment := location.equipment.get(code)) is not None:
                grid = weight_grid(equipment)
                grids.append(
                    WeightGrid(equipment_code=code, weights_kg=grid, min_step_kg=min_step(grid))
                )
        return grids

    async def plates(self, location_id: uuid.UUID, data: PlatesRequest) -> PlatesRead:
        location = to_engine_location(await self._get(location_id))
        equipment = location.equipment.get(data.equipment_code)
        if equipment is None or equipment.bar_kg is None:
            raise ValidationFailedException(
                "Для этого снаряда в локации не указаны гриф и блины",
                {"equipment_code": "Нет разборного снаряда"},
            )
        per_side = plate_breakdown(data.target_kg, equipment)
        nearest = []
        if per_side is None:
            grid = weight_grid(equipment)
            i = bisect_left(grid, data.target_kg)
            nearest = grid[max(0, i - 1) : i + 1]
        return PlatesRead(
            target_kg=data.target_kg,
            achievable=per_side is not None,
            per_side=[PlateSet(kg=p.kg, count=p.count) for p in per_side or []],
            nearest_kg=nearest,
        )

    async def _get(self, location_id: uuid.UUID) -> Location:
        location = await self.locations.get_for_user(location_id, self.user.id)
        if location is None:
            raise NotFoundException("Такой локации нет")
        return location

    async def _read(self, *locations: Location) -> list[LocationRead]:
        exercises = [to_engine_exercise(e) for e in await self.catalog.list_exercises()]
        health = (await ProfileService(self.session, self.user).get()).health_flags
        result = []
        for location in locations:
            engine_location = to_engine_location(location)
            result.append(
                LocationRead.model_validate(
                    {
                        "id": location.id,
                        "kind": location.kind,
                        "title": location.title,
                        "is_default": location.is_default,
                        "travel_minutes": location.travel_minutes,
                        "constraints": location.constraints,
                        "equipment": [
                            {
                                "equipment_code": item.equipment_code,
                                "quantity": item.quantity,
                                "details": item.details,
                            }
                            for item in location.equipment
                        ],
                        "available_exercise_count": sum(
                            is_available(e, engine_location, health) for e in exercises
                        ),
                    }
                )
            )
        return result
