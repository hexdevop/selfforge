import json
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar
from uuid import UUID

from app.cache.redis import redis_client
from app.core.config import settings

P = ParamSpec("P")
R = TypeVar("R")

_PRIMITIVE_TYPES = (str, int, float, bool, UUID, type(None))


def _stringify(value: Any) -> str:
    return str(value) if isinstance(value, UUID) else json.dumps(value)


def _default_key_builder(prefix: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Build a cache key from primitive args/kwargs, skipping `self` and non-primitives
    (e.g. a DB session) since they can't be part of a stable cache key.
    """
    parts = [_stringify(a) for a in args if isinstance(a, _PRIMITIVE_TYPES)]
    parts += [
        f"{k}={_stringify(v)}" for k, v in sorted(kwargs.items()) if isinstance(v, _PRIMITIVE_TYPES)
    ]
    return ":".join([prefix, *parts])


def cached(
    key_prefix: str,
    ttl: int | None = None,
    key_builder: Callable[[str, tuple[Any, ...], dict[str, Any]], str] = _default_key_builder,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Cache an async function's JSON-serializable return value in Redis.

    Only meant for read paths returning plain data (dicts, lists, Pydantic
    `.model_dump()`-ed payloads) — not ORM objects, which aren't JSON-safe
    and would go stale silently across requests/sessions.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            cache_key = key_builder(key_prefix, args, kwargs)

            cached_value = await redis_client.get(cache_key)
            if cached_value is not None:
                return json.loads(cached_value)  # type: ignore[no-any-return]

            result = await func(*args, **kwargs)
            await redis_client.set(
                cache_key, json.dumps(result), ex=ttl or settings.CACHE_DEFAULT_TTL_SECONDS
            )
            return result

        return wrapper

    return decorator


async def invalidate_prefix(prefix: str) -> None:
    """Delete every cache key starting with `prefix:` using SCAN (non-blocking)."""
    async for key in redis_client.scan_iter(match=f"{prefix}:*"):
        await redis_client.delete(key)
