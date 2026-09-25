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

## Cutover checklist

Do these in order. Keep `*.onrender.com` working until step 6.

1. **Pick a hostname** (example: `access.airychen.com`). Grafana / Outline can stay on
   `*.onrender.com` for the free demo.
2. **Render custom domain** — [dashboard service](https://dashboard.render.com/web/srv-dam9q3bm8hqs73d1np90) →
   **Settings → Custom Domains** → add the hostname. Hobby workspaces allow a small number of custom domains.
3. **Cloudflare DNS (grey cloud first)** — see [section 3](#3-cloudflare-dns-verify-first-then-proxy).
4. **Render Verify** — wait until the certificate is **Issued**.
5. **IdP redirect URIs** — add the new callback next to the existing onrender one (do not remove yet):
   - Google: `https://<host>/auth/callback` (+ authorized origin `https://<host>`)
   - Entra: same redirect URI
6. **Flip the app to the new origin**
   - Set `PUBLIC_BASE_URL=https://<host>` on the dashboard service (restart / redeploy).
   - Point Grafana + Outline OIDC URLs at the same host (`/oauth/authorize`, `/oauth/token`, `/oauth/userinfo`).
   - Orange-cloud the CNAME.
7. **Smoke test** — open `https://<host>`, Google + Microsoft sign-in, Ask, Grafana SSO, Outline SSO.
8. **Optional** — rate-limit `/auth/*` ([section 5](#5-rate-limits-recommended--not-a-global-challenge-page)). Update README live links.
9. **Later** — drop the old onrender redirect URIs from Google/Entra once you no longer need them.

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
| Grafana / Outline | Auth / token / userinfo URLs must use the same public origin (`PUBLIC_BASE_URL`). App home URLs can stay on `*.onrender.com`. |

`start.sh` still runs migrations; no schema change for Cloudflare itself.

CORS already allows both `PUBLIC_BASE_URL` and `RENDER_EXTERNAL_URL` during the cutover window.

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
