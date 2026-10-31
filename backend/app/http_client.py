"""Client IP helpers when the app sits behind Cloudflare and Render's proxy.

Request path in production: visitor -> Cloudflare -> Render load balancer -> app.
Render appends the address that connected to it to ``X-Forwarded-For``, so the
rightmost public entry is the real peer. Anything to the left of it, and
``CF-Connecting-IP``, was written by whoever connected, so they are only
trusted when that peer is a Cloudflare edge. Otherwise a direct request to
the ``onrender.com`` origin could pick any IP, dodging rate limits and
polluting the audit log.
"""

from __future__ import annotations

import ipaddress
from functools import lru_cache

from fastapi import Request

# https://www.cloudflare.com/ips/ (stable for years; update if Cloudflare adds ranges)
_CLOUDFLARE_RANGES = (
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
)
_CLOUDFLARE_NETS = tuple(ipaddress.ip_network(cidr) for cidr in _CLOUDFLARE_RANGES)


def _parse(value: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not value:
        return None
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


# Hops inside Render's network (and local development). Deliberately explicit:
# ipaddress.is_private also covers documentation ranges and more.
_INTERNAL_NETS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)


def _is_internal(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(ip in net for net in _INTERNAL_NETS)


@lru_cache(maxsize=4096)
def is_cloudflare(ip: str) -> bool:
    parsed = _parse(ip)
    return parsed is not None and any(parsed in net for net in _CLOUDFLARE_NETS)


def _peer(request: Request) -> str | None:
    """The public address that actually connected to our infrastructure."""
    direct = request.client.host if request.client else None
    direct_ip = _parse(direct)
    if direct_ip is not None and not _is_internal(direct_ip):
        return str(direct_ip)
    # Behind Render's proxy: walk X-Forwarded-For from the right, skipping
    # internal hops, to the entry Render itself recorded.
    forwarded = request.headers.get("x-forwarded-for") or ""
    for hop in reversed(forwarded.split(",")):
        ip = _parse(hop)
        if ip is not None and not _is_internal(ip):
            return str(ip)
    return direct


def client_ip(request: Request) -> str | None:
    """Best-effort visitor IP for audit logs and rate limiting."""
    peer = _peer(request)
    if peer and is_cloudflare(peer):
        cf = _parse(request.headers.get("cf-connecting-ip"))
        if cf is not None:
            return str(cf)
    return peer[:64] if peer else None
