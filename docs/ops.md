# How I'd run this in production (and what I'm defending against)

Short version of how I think about operating this app. The live demos are free-tier; the habits below are what I'd keep if this were a real customer-facing tenant portal.

## Trust boundaries

```
Browser ──HTTPS──▶ App (FastAPI + React, one origin)
                      │
                      ├── session cookie (HttpOnly, SameSite=Lax, Secure in prod)
                      ├── OIDC code flow ──▶ Google / Entra        (we are the client)
                      ├── /oauth/* ◀── Grafana & other apps        (we are the provider)
                      └── SQL ──▶ Postgres (FORCE RLS on tenant tables)
```

- **Tenant isolation** lives in Postgres RLS (`app.tenant_id`), not only in Python `WHERE` clauses. A missing filter in app code should still return nothing.
- **Identity** is delegated to Google / Entra. We store `idp` + `oidc_sub`, not passwords. Email domain maps the user to a tenant.
- **Session** is a signed cookie carrying `user_id` / `tenant_id` / `role`. Secret stays in env (`SESSION_SECRET`); Render generates it, Fly gets its own (cookies aren't shared across hosts anyway).

## What I already do

| Control | Where |
| --- | --- |
| FORCE RLS on `users`, `audit_events`, `oauth_clients`, `app_grants`, `oauth_codes` | Alembic migrations |
| Provider: PKCE S256 when sent (optional for confidential clients — Outline omits it), codes hashed + single-use + 60 s TTL, client secrets hashed, exact redirect match | `app/oauth/service.py`, `api/oauth.py` |
| Provider: RS256 keys in Postgres, JWKS published, retired keys kept 24 h | `app/oauth/keys.py` |
| App sign-ins and denials audited with the reason (`app_login`, `app_login_denied`) | `audit_events.details` |
| OIDC redirect URI is server-configured (not user input) | `config.py` / Authlib |
| CORS allowlist + credentials only for our origins | `main.py` |
| Secure cookies in production | `SessionMiddleware` (`https_only`) |
| Failed + successful sign-ins audited per tenant; access disable/enable audited | `audit_events` |
| JSON logs + `X-Request-ID` | observability middleware |
| `/health` checks DB (used by Render/Fly probes) | `GET /health` |
| Secrets via env / platform secret stores, not git | Render Blueprint, Fly secrets, `.env` gitignored |
| Basic browser hardening headers | `SecurityHeadersMiddleware` |
| Real visitor IP when behind Cloudflare (`CF-Connecting-IP`) | `app/http_client.py` → audit |

## Threats I care about here

1. **Cross-tenant data leak** — mitigated by FORCE RLS + CI tests as a non-superuser. Superuser DB access bypasses RLS; production app DB roles must not be superuser.
2. **OIDC / redirect abuse** — redirect URI is fixed per host (`RENDER_EXTERNAL_URL` / `PUBLIC_BASE_URL`). Both production URLs must be registered at the IdP.
3. **Session theft** — HttpOnly + Secure + HTTPS-only hosts. Still vulnerable to XSS in our own origin; keep the SPA dependency surface small and avoid `eval`-style patterns.
4. **Credential stuffing / login spam** — edge rate limits on `/auth/login` and `/auth/callback` via Cloudflare (see [`docs/cloudflare.md`](cloudflare.md)). App-level limits can still be added later as defense in depth.
5. **Identity conflict** (same email+IdP, different `sub`) — we reject and audit rather than silently merge. That's intentional.
6. **Stale access** — owners and admins can disable users in People; login and existing sessions are rejected (`user_disabled`). The company **owner** (first user on the tenant) can promote/demote admins; promoted admins can only disable members. You can't disable yourself, the owner, or the last active admin.
7. **Public `/health`** — exposes DB up/down only; fine for probes. Don't hang richer internals off it.
8. **Open redirect via `/oauth/authorize`** — `redirect_uri` must equal a registered URI byte-for-byte; unknown clients or URIs land on our own error page, never on the attacker's URL.
9. **Code interception / replay** — PKCE S256 is enforced when the RP sends a challenge (Grafana does); confidential clients that omit PKCE (Outline) still need the client secret. Codes are hashed at rest and burned on first use *or* first failed attempt.
10. **Cross-tenant app access** — the token endpoint resolves `client_id → tenant_id` through `oauth_client_lookup` (public, no secrets) and sets RLS before reading anything else. A user from tenant B hitting tenant A's app is denied with `wrong_tenant` and audited under A.
11. **Stale access to apps** — a disabled user is rejected at authorize, token and userinfo. Existing Grafana sessions live until Grafana's own session expires; for a hard cut I'd add a back-channel logout or shorten the RP session.
12. **Signing key compromise** — rotate by inserting a new `signing_keys` row and setting `retired_at` on the old one; the old public key stays in JWKS for 24 h so in-flight tokens still verify, then disappears. Tokens live 1 h.

## Ops habits

- **Migrations** run on container start (`start.sh` / Alembic). Treat schema changes as part of the deploy.
- **Backups** — use the host's Postgres backups (Render snapshots / paid plan). Free Postgres expires; don't treat it as durable without an upgrade path.
- **Cold starts** — Render free sleeps (~30 s wake). Fly with `min_machines_running = 0` wakes faster but still not zero. For a real SLA: keep one machine warm or pay for always-on.
- **Two hosts, one DB (demo)** — Fly can reuse Render's external `DATABASE_URL`. Fine for a portfolio; in production I'd give each environment its own database and secrets.
- **Edge / DNS** — optional Cloudflare in front of the dashboard: Active zone, Full (strict) SSL, rate limits on `/auth/*`, no site-wide bot challenge (see [`docs/cloudflare.md`](cloudflare.md)).
- **IdP apps** — Google + Entra registrations are part of the system. Document who owns them; rotate client secrets like any other credential.
- **Relying parties** — each registered app's secret is shown once; rotate from the Apps menu and paste into the RP. The Grafana demo runs on Render's free tier with SQLite, so its user table is ephemeral — that is fine because users are re-created from our claims on every sign-in.
- **Expired auth codes** — purged opportunistically per tenant on each successful authorize (rows older than 10 min past expiry). A cron would be cleaner at scale.

## Infra path

Live Render demo: **Blueprint** (`render.yaml`). Optional state-managed twin: **`infra/render`** (Terraform). Fly: **`fly.toml` + flyctl** (see `/infra/README.md` for why not Terraform-on-Fly yet).
