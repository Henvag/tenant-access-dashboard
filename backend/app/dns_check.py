"""TXT lookups for domain verification, over DNS-over-HTTPS.

DoH goes out as an ordinary HTTPS request, so it works on hosts without a
usable resolver for TXT records and needs no extra dependency.
"""

from __future__ import annotations

import httpx

DOH_URL = "https://cloudflare-dns.com/dns-query"
TXT_TYPE = 16


class DnsLookupError(Exception):
    pass


async def txt_records(name: str) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                DOH_URL,
                params={"name": name, "type": "TXT"},
                headers={"accept": "application/dns-json"},
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise DnsLookupError("dns_lookup_failed") from exc
    values: list[str] = []
    for answer in data.get("Answer") or []:
        if answer.get("type") != TXT_TYPE:
            continue
        raw = str(answer.get("data") or "")
        # Long TXT values arrive as several quoted strings: "abc" "def".
        parts = [chunk for chunk in raw.split('"') if chunk.strip()]
        values.append("".join(parts) if parts else raw)
    return values
