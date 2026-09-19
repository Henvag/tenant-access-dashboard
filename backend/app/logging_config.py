import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """One JSON object per line — easy to ship to log drains on Render/Fly."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if getattr(record, "request_id", None):
            payload["request_id"] = record.request_id
        if getattr(record, "method", None):
            payload["method"] = record.method
        if getattr(record, "path", None):
            payload["path"] = record.path
        if getattr(record, "status_code", None) is not None:
            payload["status_code"] = record.status_code
        if getattr(record, "duration_ms", None) is not None:
            payload["duration_ms"] = record.duration_ms
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        from app.observability import get_request_id

        record.request_id = get_request_id()
        return True


def configure_logging(*, json_logs: bool) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(levelname)s %(name)s [req=%(request_id)s] %(message)s")
        )
    root.addHandler(handler)

    # Keep noisy libraries quieter unless they error.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
