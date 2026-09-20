"""In-process rate limiter unit tests (no DB)."""

from starlette.requests import Request

from app.rate_limit import SlidingWindowLimiter, auth_limiter, rate_limit_auth
import pytest
from fastapi import HTTPException


def test_sliding_window_allows_then_blocks() -> None:
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
    assert limiter.allow("a")
    assert limiter.allow("a")
    assert limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")


def test_keys_are_independent() -> None:
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
    assert limiter.allow("one")
    assert not limiter.allow("one")
    assert limiter.allow("two")


@pytest.mark.asyncio
async def test_rate_limit_auth_dependency_raises() -> None:
    auth_limiter.reset()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/auth/login",
        "raw_path": b"/auth/login",
        "query_string": b"",
        "headers": [(b"cf-connecting-ip", b"203.0.113.50")],
        "client": ("10.0.0.1", 443),
        "server": ("test", 443),
    }
    request = Request(scope)
    for _ in range(30):
        await rate_limit_auth(request)
    with pytest.raises(HTTPException) as exc:
        await rate_limit_auth(request)
    assert exc.value.status_code == 429
    assert exc.value.detail == "rate_limited"
    auth_limiter.reset()
