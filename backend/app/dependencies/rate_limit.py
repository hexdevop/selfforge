from collections.abc import Awaitable, Callable

from fastapi import Request

from app.cache.redis import redis_client
from app.core.exceptions import TooManyRequestsException


def rate_limit(scope: str, limit: int, window_seconds: int) -> Callable[[Request], Awaitable[None]]:
    """Fixed-window limiter per client IP, backed by Redis.

    Behind a reverse proxy, run uvicorn with `--proxy-headers` so `request.client`
    is the real client address and not the proxy's.
    """

    async def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"rate:{scope}:{ip}"
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds, nx=True)
            count, _ = await pipe.execute()
        if count > limit:
            raise TooManyRequestsException()

    return dependency
