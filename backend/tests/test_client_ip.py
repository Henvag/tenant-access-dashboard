"""Unit tests for reverse-proxy client IP resolution (no DB)."""

from starlette.requests import Request

from app.http_client import client_ip


def _request(headers: dict[str, str], peer: str = "10.0.0.1") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (peer, 443),
        "server": ("test", 443),
    }
    return Request(scope)


def test_prefers_cf_connecting_ip() -> None:
    req = _request(
        {
            "cf-connecting-ip": "203.0.113.9",
            "x-forwarded-for": "198.51.100.1, 10.0.0.2",
        }
    )
    assert client_ip(req) == "203.0.113.9"


def test_falls_back_to_x_forwarded_for() -> None:
    req = _request({"x-forwarded-for": "198.51.100.7, 10.0.0.2"})
    assert client_ip(req) == "198.51.100.7"


def test_falls_back_to_peer() -> None:
    req = _request({}, peer="192.0.2.44")
    assert client_ip(req) == "192.0.2.44"
