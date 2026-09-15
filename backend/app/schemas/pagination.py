from pydantic import BaseModel, ConfigDict, Field, computed_field


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size


class Page[T](BaseModel):
    """Generic page of items.

    `arbitrary_types_allowed` is needed because `Page[SomeSqlAlchemyModel]`
    is used internally (repository/service layer) before being re-validated
    into `Page[SomeReadSchema]` at the API boundary.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T]
    total: int
    page: int
    size: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pages(self) -> int:
        return (self.total + self.size - 1) // self.size if self.size else 0

    @classmethod
    def create(cls, items: list[T], total: int, params: PageParams) -> "Page[T]":
        return cls(items=items, total=total, page=params.page, size=params.size)
