import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.logging_config import JsonFormatter, configure_logging
from app.observability import RequestIdMiddleware, get_request_id


def test_json_formatter_includes_request_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request",
        args=(),
        exc_info=None,
    )
    record.request_id = "abc123"
    record.method = "GET"
    record.path = "/health"
    record.status_code = 200
    record.duration_ms = 12.5
    payload = json.loads(formatter.format(record))
    assert payload["msg"] == "request"
    assert payload["request_id"] == "abc123"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 12.5


def test_request_id_middleware_sets_header():
    configure_logging(json_logs=False)
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/ping")
    async def ping():
        return {"request_id": get_request_id()}

    client = TestClient(app)
    response = client.get("/ping", headers={"X-Request-ID": "client-req-1"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "client-req-1"
    assert response.json()["request_id"] == "client-req-1"


@pytest.mark.asyncio
async def test_health_ok_when_database_up(monkeypatch):
    from app import main

    async def ok() -> bool:
        return True

    monkeypatch.setattr(main, "database_reachable", ok)
    transport_app = main.app
    # Lifespan configures logging/oauth; TestClient handles it.
    with TestClient(transport_app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_health_degraded_when_database_down(monkeypatch):
    from app import main

    async def down() -> bool:
        return False

    monkeypatch.setattr(main, "database_reachable", down)
    with TestClient(main.app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
