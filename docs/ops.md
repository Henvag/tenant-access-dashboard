# How I'd run this in production (and what I'm defending against)

Short version of how I think about operating this app. The live demos are free-tier; the habits below are what I'd keep if this were a real customer-facing tenant portal.

## Trust boundaries

```
Browser ──HTTPS──▶ App (FastAPI + React, one origin)
                      │
                      ├── session cookie (HttpOnly, SameSite=Lax, Secure in prod)
                      ├── OIDC code flow ──▶ Google / Entra
                      └── SQL ──▶ Postgres (FORCE RLS on tenant tables)
```

- **Tenant isolation** lives in Postgres RLS (`app.tenant_id`), not only in Python `WHERE` clauses. A missing filter in app code should still return nothing.
- **Identity** is delegated to Google / Entra. We store `idp` + `oidc_sub`, not passwords. Email domain maps the user to a tenant.
- **Session** is a signed cookie carrying `user_id` / `tenant_id` / `role`. Secret stays in env (`SESSION_SECRET`); Render generates it, Fly gets its own (cookies aren't shared across hosts anyway).

## What I already do

| Control | Where |
| --- | --- |
| FORCE RLS on `users` and `audit_events` | Alembic migrations |
| OIDC redirect URI is server-configured (not user input) | `config.py` / Authlib |
| CORS allowlist + credentials only for our origins | `main.py` |
| Secure cookies in production | `SessionMiddleware` (`https_only`) |
| Failed + successful sign-ins audited per tenant | `audit_events` |
| JSON logs + `X-Request-ID` | observability middleware |
| `/health` checks DB (used by Render/Fly probes) | `GET /health` |
| Secrets via env / platform secret stores, not git | Render Blueprint, Fly secrets, `.env` gitignored |
| Basic browser hardening headers | `SecurityHeadersMiddleware` |

## Threats I care about here

1. **Cross-tenant data leak** — mitigated by FORCE RLS + CI tests as a non-superuser. Superuser DB access bypasses RLS; production app DB roles must not be superuser.
2. **OIDC / redirect abuse** — redirect URI is fixed per host (`RENDER_EXTERNAL_URL` / `PUBLIC_BASE_URL`). Both production URLs must be registered at the IdP.
3. **Session theft** — HttpOnly + Secure + HTTPS-only hosts. Still vulnerable to XSS in our own origin; keep the SPA dependency surface small and avoid `eval`-style patterns.
4. **Credential stuffing / login spam** — **not rate-limited yet**. I'd put a reverse-proxy or app-level limit on `/auth/login/*` and `/auth/callback` before calling this production-grade.
5. **Identity conflict** (same email+IdP, different `sub`) — we reject and audit rather than silently merge. That's intentional.
6. **Public `/health`** — exposes DB up/down only; fine for probes. Don't hang richer internals off it.

## Ops habits

- **Migrations** run on container start (`start.sh` / Alembic). Treat schema changes as part of the deploy.
- **Backups** — use the host's Postgres backups (Render snapshots / paid plan). Free Postgres expires; don't treat it as durable without an upgrade path.
- **Cold starts** — Render free sleeps (~30 s wake). Fly with `min_machines_running = 0` wakes faster but still not zero. For a real SLA: keep one machine warm or pay for always-on.
- **Two hosts, one DB (demo)** — Fly can reuse Render's external `DATABASE_URL`. Fine for a portfolio; in production I'd give each environment its own database and secrets.
- **IdP apps** — Google + Entra registrations are part of the system. Document who owns them; rotate client secrets like any other credential.

## Infra path

Live Render demo: **Blueprint** (`render.yaml`). Optional state-managed twin: **`infra/render`** (Terraform). Fly: **`fly.toml` + flyctl** (see `/infra/README.md` for why not Terraform-on-Fly yet).
