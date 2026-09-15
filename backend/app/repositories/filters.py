"""Django-style dict filters for SQLAlchemy select statements.

Usage: `{"is_active": True, "created_at__gte": some_date, "email__ilike": "%gmail%"}`.
Keys without `__` default to equality; the suffix after `__` picks the operator.
"""

from typing import Any

from sqlalchemy import ColumnElement, Select
from sqlalchemy.orm import DeclarativeBase

_OPERATORS: dict[str, str] = {
    "eq": "__eq__",
    "ne": "__ne__",
    "gt": "__gt__",
    "gte": "__ge__",
    "lt": "__lt__",
    "lte": "__le__",
}


def _build_condition(column: Any, operator: str, value: Any) -> ColumnElement[bool]:
    if operator in _OPERATORS:
        return getattr(column, _OPERATORS[operator])(value)  # type: ignore[no-any-return]
    if operator == "in":
        return column.in_(value)  # type: ignore[no-any-return]
    if operator == "not_in":
        return column.not_in(value)  # type: ignore[no-any-return]
    if operator == "like":
        return column.like(value)  # type: ignore[no-any-return]
    if operator == "ilike":
        return column.ilike(value)  # type: ignore[no-any-return]
    if operator == "is_null":
        return column.is_(None) if value else column.is_not(None)  # type: ignore[no-any-return]

    raise ValueError(f"Unsupported filter operator: {operator!r}")


def apply_filters(
    stmt: Select[Any], model: type[DeclarativeBase], filters: dict[str, Any]
) -> Select[Any]:
    for key, value in filters.items():
        if value is None:
            continue

        field_name, _, operator = key.partition("__")
        operator = operator or "eq"

        if not hasattr(model, field_name):
            raise ValueError(f"Unknown filter field: {field_name!r} on {model.__name__}")

        column = getattr(model, field_name)
        stmt = stmt.where(_build_condition(column, operator, value))

    return stmt
