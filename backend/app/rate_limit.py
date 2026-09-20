"""Simple per-IP sliding-window rate limits (in-process; fine for one free-tier instance)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

from app.http_client import client_ip


class SlidingWindowLimiter:
    def __init__(self, *, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# Auth start + callback: generous enough for real users, tight enough for stuffing.
auth_limiter = SlidingWindowLimiter(limit=30, window_seconds=60)
# Token endpoint: codes are single-use; still blunt credential/code spraying.
token_limiter = SlidingWindowLimiter(limit=60, window_seconds=60)


def _key(request: Request, prefix: str) -> str:
    ip = client_ip(request) or "unknown"
    return f"{prefix}:{ip}"


async def rate_limit_auth(request: Request) -> None:
    if not auth_limiter.allow(_key(request, "auth")):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limited",
        )


async def rate_limit_token(request: Request) -> None:
    if not token_limiter.allow(_key(request, "token")):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limited",
        )
