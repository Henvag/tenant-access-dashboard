"""Unit tests for reverse-proxy client IP resolution (no DB)."""

from starlette.requests import Request

from app.http_client import client_ip

CF_EDGE = "172.70.1.2"  # inside Cloudflare's 172.64.0.0/13
RENDER_HOP = "10.0.0.2"


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


def test_uses_cf_connecting_ip_when_request_came_through_cloudflare() -> None:
    req = _request(
        {
            "cf-connecting-ip": "203.0.113.9",
            "x-forwarded-for": f"203.0.113.9, {CF_EDGE}, {RENDER_HOP}",
        }
    )
    assert client_ip(req) == "203.0.113.9"


def test_ignores_spoofed_cf_header_on_direct_origin_request() -> None:
    # Someone calls the onrender.com origin directly and makes up both headers.
    req = _request(
        {
            "cf-connecting-ip": "1.2.3.4",
            "x-forwarded-for": "1.2.3.4, 198.51.100.66",
        }
    )
    assert client_ip(req) == "198.51.100.66"


def test_ignores_spoofed_leftmost_forwarded_for() -> None:
    req = _request({"x-forwarded-for": "1.2.3.4, 198.51.100.7, 10.0.0.2"})
    assert client_ip(req) == "198.51.100.7"


def test_ipv6_cloudflare_edge() -> None:
    req = _request(
        {
            "cf-connecting-ip": "2a01:799:ba0:901::1",
            "x-forwarded-for": "2a01:799:ba0:901::1, 2400:cb00:1::5",
        }
    )
    assert client_ip(req) == "2a01:799:ba0:901::1"


def test_invalid_cf_header_falls_back_to_edge() -> None:
    req = _request({"cf-connecting-ip": "not-an-ip", "x-forwarded-for": CF_EDGE})
    assert client_ip(req) == CF_EDGE


def test_public_direct_peer_wins_over_headers() -> None:
    req = _request({"x-forwarded-for": "1.2.3.4", "cf-connecting-ip": "1.2.3.4"}, peer="192.0.2.44")
    assert client_ip(req) == "192.0.2.44"


def test_internal_peer_without_headers() -> None:
    req = _request({}, peer="10.0.0.9")
    assert client_ip(req) == "10.0.0.9"
