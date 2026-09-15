import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_ctx

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a request id to every request: reuse an inbound header if present,
    otherwise generate one. Exposed via a contextvar so log lines can include it,
    and echoed back in the response header for client-side correlation.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
        token = request_id_ctx.set(request_id)

        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
