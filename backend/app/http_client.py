"""Client IP helpers when the app sits behind Cloudflare or another reverse proxy."""

from __future__ import annotations

from fastapi import Request


def client_ip(request: Request) -> str | None:
    """Best-effort visitor IP for audit logs.

    Prefer Cloudflare's ``CF-Connecting-IP`` (set at the edge; not client-spoofable
    when traffic actually went through Cloudflare). Fall back to the first
    ``X-Forwarded-For`` hop, then the direct socket peer.
    """
    cf = (request.headers.get("cf-connecting-ip") or "").strip()
    if cf:
        return cf[:64]

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:64]

    if request.client and request.client.host:
        return request.client.host[:64]
    return None
