from typing import Annotated

from fastapi import Query

from app.schemas.pagination import PageParams

Pagination = Annotated[PageParams, Query()]
