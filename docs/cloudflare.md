# Cloudflare in front of Tenant Access

Edge DNS + proxy for credibility and basic abuse resistance — **not** a replacement
for Google/Microsoft sign-in or this app’s OIDC provider. Skip Cloudflare Access /
Zero Trust as the login gate; that would compete with the product story.

## Goal

```
Browser ──HTTPS──▶ Cloudflare (proxy + optional rate limits)
                       │
                       └──HTTPS──▶ Render (tenant-access-dashboard.onrender.com)
```

What you get: Active zone, Universal SSL, real visitor IPs in audit (`CF-Connecting-IP`),
optional rate limits on `/auth/*`. What you skip by default: the “Verifying you are human”
interstitial on every visit (breaks OAuth redirects if misapplied).

## 1. Pick a hostname

Example: `access.airychen.com` → dashboard (keep `*.onrender.com` working until cutover).

Grafana / Outline can stay on `*.onrender.com` for the free demo, or get their own
subdomains later (`grafana.…`, `wiki.…`) the same way.

## 2. Add the custom domain on Render

1. Render → **tenant-access-dashboard** → **Settings → Custom Domains** → add the hostname.
2. Note the target (usually `tenant-access-dashboard.onrender.com`).

Hobby workspaces have a small custom-domain limit — check before adding many hosts.

## 3. Cloudflare DNS (verify first, then proxy)

Follow [Render’s Cloudflare guide](https://render.com/docs/configure-cloudflare-dns):

1. Cloudflare → your zone → **SSL/TLS** → encryption mode **Full** (use **Full (strict)** once Render shows a valid cert).
2. **DNS → Records** → CNAME:
   - **Name:** `access` (or `@` for apex)
   - **Target:** `tenant-access-dashboard.onrender.com`
   - **Proxy status: DNS only** (grey cloud) until Render verifies and issues the cert
3. Remove any `AAAA` records for that name (Render is IPv4-only for this path).
4. In Render, **Verify** the domain and wait until the certificate is issued.
5. Flip the CNAME to **Proxied** (orange cloud).

Zone **Status: Active** in Cloudflare is the “verified” state for DNS. There is no
end-user “Cloudflare verified” badge in the browser — just normal HTTPS.

## 4. Point the app and IdPs at the new origin

After the custom domain is live:

| Where | What |
| --- | --- |
| Render env | Set `PUBLIC_BASE_URL=https://access.airychen.com` (or your host). Redeploy / restart so OIDC redirect + issuer use it. |
| Google OAuth client | Add `https://access…/auth/callback` (keep the old onrender callback until you drop it). |
| Microsoft Entra app | Same for the Entra redirect URI. |
| Registered apps (Grafana, Outline, …) | Issuer / auth / token / userinfo URLs must use the public origin people actually open. |

`start.sh` still runs migrations; no schema change for Cloudflare itself.

## 5. Rate limits (recommended) — not a global challenge page

In Cloudflare → **Security → WAF** (or **Rate limiting** rules):

**Do**

- Rate-limit `http.request.uri.path contains "/auth/login"` and `/auth/callback` (e.g. ~30 req / 1 min / IP).
- Optionally rate-limit `/oauth/token` similarly (confidential clients + PKCE already constrain abuse).

**Don’t (for this product)**

- **I’m Under Attack!** as the default security level.
- Site-wide Bot Fight that challenges every HTML navigation.
- Managed Challenge in front of `/oauth/authorize` or `/oauth/callback`-style RP redirects — Google/Microsoft and Grafana/Outline round-trips will look “broken.”

The orange “Verifying you are human…” screen is fine for a **Register** page later
(Turnstile) or emergency attack mode — not for the happy-path SSO flow.

## 6. Optional hardening later

- Turnstile on company registration only.
- Cache rules: cache `/assets/*` at the edge; bypass everything under `/auth`, `/oauth`, `/api`-style JSON.
- Screenshot for the portfolio: zone Active + Full (strict) + one rate-limit rule.

## What the app already does for Cloudflare

Audit logging prefers `CF-Connecting-IP` when present (`app/http_client.py`), so People /
Audit show the visitor’s real IP instead of a Cloudflare anycast address once the
orange cloud is on.
