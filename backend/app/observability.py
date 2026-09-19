import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_request_id: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("app.request")


def get_request_id() -> str:
    return _request_id.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    header_name = "X-Request-ID"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = (request.headers.get(self.header_name) or "").strip()
        request_id = incoming[:128] if incoming else uuid.uuid4().hex
        token = _request_id.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            logger.exception(
                "request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "request_id": request_id,
                },
            )
            raise
        else:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            # Skip noisy static asset chatter in access logs.
            if not request.url.path.startswith("/assets/"):
                logger.info(
                    "request",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "request_id": request_id,
                    },
                )
            response.headers[self.header_name] = request_id
            return response
        finally:
            _request_id.reset(token)
