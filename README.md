# Tenant Access Dashboard

I wanted a small, finished project that shows how I think about multi-tenant SaaS: identity, isolation, and shipping the same app without locking it to one host.

**Idea:** a company registers. People sign in with Google or Microsoft. An admin can see who has access — and cannot see another company's people, even if the app code forgets a filter. The dashboard is also an **OpenID Connect provider**: register Grafana (or any OIDC app) under **Apps**, decide who may use it, and your team signs in to it with the same account. Every sign-in and denial lands in the audit log.

[![CI](https://github.com/Henvag/tenant-access-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/Henvag/tenant-access-dashboard/actions/workflows/ci.yml)

**Why both Render and Fly?** Not because I need two demos — because I wanted to show the app isn't married to one cloud. Same multi-stage `Dockerfile`, same migrations and OIDC config; Render is a PaaS blueprint (`render.yaml`), Fly is a container platform (`fly.toml` + `fly deploy`). If the image is portable, switching hosts is mostly secrets and a redirect URI.

| | URL | Role |
| --- | --- | --- |
| **Render** | https://tenant-access-dashboard.onrender.com | Primary demo / blueprint deploy. Free tier — cold start can take ~30 s |
| **Fly.io** | https://tenant-access-dashboard.fly.dev | Same image on a second hosting model |
| **Grafana** | https://tenant-access-grafana.onrender.com | Demo app that signs in *through* the dashboard (SSO + role mapping) |
| **Outline** | https://tenant-access-outline.onrender.com | Notion-like wiki, same OIDC provider (second relying party) |

---

## Screenshots

| Landing / sign-in | Admin overview |
| --- | --- |
| ![Landing](docs/screenshots/landing.png) | ![Overview](docs/screenshots/overview.png) |

| People (admin) | Norwegian UI |
| --- | --- |
| ![People](docs/screenshots/people.png) | ![NO](docs/screenshots/norwegian.png) |

## Try it

1. Open either link → **Register company** with your email domain (`gmail.com` or `outlook.com` works fine for a personal demo).
2. Sign in with **Google** or **Microsoft**. First person on that domain becomes admin.
3. **Overview** is stats + recent activity. **People** is the directory — the company **owner** (first signer) can **Promote** / **Demote** and **Disable** access; promoted admins can disable members. **Audit** shows sign-ins, failures, and access/role changes.
4. **Apps** (admin): register an OIDC app, pick who can use it (everyone / admins / assigned people), copy the client id + secret. Everyone gets a **Your apps** launcher on the Overview.
5. Open the Grafana or Outline demo → **Sign in with Tenant Access**. Grafana maps roles (Admin / Editor / Viewer). Outline is a Notion-style wiki using the same IdP. Try a user who isn't assigned — denial lands in **Audit**.
6. Register a second company on a different domain and sign in there. You should only see that tenant — including its apps.

There's an **EN / NO** language toggle if you want to poke at the UI.

---

## Why RLS, not just `WHERE tenant_id = ?`

The classic multi-tenant bug is forgetting the tenant filter somewhere. I put isolation in Postgres so the database refuses to leak rows:

```sql
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;   -- even the table owner

CREATE POLICY users_tenant_isolation ON users
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
```

On every request that needs tenant data I set the context for that transaction:

```python
await session.execute(
    text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
    {"tenant_id": str(tenant_id)},
)
```

No context → empty reads and rejected writes. CI runs the RLS tests as a normal DB role, not a superuser (superusers bypass RLS and would fake the result).

## Sign-in → tenant

```
Google or Entra (OIDC) ──id_token──▶ FastAPI ──▶ email domain ──▶ tenant
```

Roughly:

1. Company registers a domain (`acme.com`).
2. User picks Google or Microsoft. Authlib handles the OIDC flow; both IdPs land on the same `/auth/callback`.
3. Email domain (or Google Workspace `hd`) has to match a registered tenant.
4. User is created/updated **inside** that tenant's RLS context, stored with `idp` + `oidc_sub`. First user gets admin. Same email via the other IdP links to the same person. I write audit events for success and for failed sign-ins when we know the tenant.
5. Session cookie holds `user_id` + `tenant_id`; later requests re-apply RLS from that.

Roles are deliberately just `admin` and `user` (plus the tenant **owner**, the first admin). I kept the surface small on purpose.

## Being the identity provider

Consuming OIDC from Google is table stakes; the interesting half of an identity product is *issuing* identity to other apps. So the dashboard also speaks OIDC outward:

```
Grafana ──/oauth/authorize──▶ dashboard  (session? tenant? disabled? policy?)
        ◀─────code────────────           audit: app_login / app_login_denied
Grafana ──/oauth/token (secret + PKCE)──▶ RS256 id_token + access_token
Grafana ──/oauth/userinfo─────────────▶ email, name, role, tenant
```

- **Discovery + JWKS** at `/.well-known/openid-configuration` and `/.well-known/jwks.json`. Signing keys are RSA-2048, stored in Postgres (both hosts have ephemeral disks), cached in memory, rotatable.
- **Authorization code + PKCE (S256) only.** Codes are hashed at rest, single-use, live 60 s, and are burned on any failed exchange. Client secrets are stored hashed.
- **Redirect URIs must match exactly.** An unregistered URI never gets a redirect — the user sees a dashboard error page instead.
- **Access policy per app:** everyone, admins only, or an explicit list of people. Denials say why (`not_assigned`, `admins_only`, `user_disabled`, `wrong_tenant`, `app_disabled`).
- **Role claim** is `owner` / `admin` / `member`, so relying parties can map it. Grafana turns that into Admin / Editor / Viewer via `GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH`.
- **RLS still applies.** Clients, grants and codes are tenant tables under FORCE RLS. The unauthenticated token endpoint resolves `client_id → tenant_id` through a tiny secret-free lookup table, sets the tenant, and only then reads the protected rows.
- **Not signed in yet?** The authorize request is parked in the session; after Google/Microsoft sign-in the callback resumes it, so "Sign in to continue to Grafana" is a real flow, not a dead end.

## What I used

| | | Why I picked it |
| --- | --- | --- |
| API | FastAPI, SQLAlchemy 2 async, Alembic | Comfortable, typed, good async Postgres story |
| Auth | Authlib (Google + Entra ID) | One OIDC path for two IdPs |
| OIDC provider | joserfc (RS256 JWT/JWKS), PKCE | Issue tokens to apps like Grafana; keys live in Postgres |
| DB | PostgreSQL 16 + RLS | Isolation where I can't forget it |
| UI | React + TypeScript + Vite | Built into the API image — one origin, one cookie |
| Ship | Docker, GitHub Actions, Render + Fly | One image, two hosting models (PaaS vs containers) |
| Ops | JSON logs, request IDs, `/health`, basic security headers | Something useful when the free tier misbehaves |

One container builds the frontend, copies it in, runs migrations on start, and serves everything.

## Layout

```
backend/
  app/
    api/         auth, tenants, users, audit, apps, oauth (provider)
    auth/        identity, oidc, rls, audit
    oauth/       signing keys, PKCE, codes, access policy
    models/      Tenant, User, AuditEvent, OAuthClient, AppGrant, OAuthCode, SigningKey
    config.py    public URL from RENDER_EXTERNAL_URL or PUBLIC_BASE_URL
  alembic/
  tests/
frontend/        EN/NO i18n, dashboard, landing
Dockerfile · docker-compose.yml · render.yaml · fly.toml
infra/render/  Terraform twin of the Render Blueprint (optional)
docs/ops.md    How I'd run this + threat notes
.github/workflows/ci.yml
```

---

## Run it yourself

**Docker** (easiest):

```powershell
docker compose up --build
```

Then http://localhost:8000. Postgres is on host port **5433**.  
Redirect URI for both IdPs: `http://localhost:8000/auth/callback`.

**Without Docker:** Postgres 16, Python 3.12, Node 22.

```powershell
cd backend
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

### Google

Create a Web OAuth client. Origins: `http://localhost:5173`, `http://localhost:8000` (plus the production URLs below). Redirect: `http://localhost:8000/auth/callback`. Add yourself as a test user on the consent screen.

### Microsoft Entra

I used a free personal Microsoft account — no paid Azure subscription for app registration.

1. [Entra admin center](https://entra.microsoft.com) → App registrations → New
2. Accounts: any org directory **and** personal Microsoft accounts
3. Redirect (Web): `http://localhost:8000/auth/callback`
4. Client secret → `ENTRA_CLIENT_ID` / `ENTRA_CLIENT_SECRET`. Leave `ENTRA_TENANT_ID=common`
5. If email is missing on the token, add the optional `email` claim under Token configuration

`outlook.com` / `hotmail.com` / `live.com` all normalize to `outlook.com` when you register.

## Tests & CI

```powershell
cd backend
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/access_dashboard_test"
.\.venv\Scripts\pytest
```

I care most that tenant A cannot see B's users, audit rows or apps, and that no tenant context fails closed. The provider tests run the whole code flow over HTTP: register app → denied → grant → code → token (Basic auth + PKCE) → userinfo → replayed code rejected → audit rows present.

Every push runs pytest, a frontend production build, and a Docker build. Render redeploys `main` from the blueprint.

---

## Deploy

### Render

1. Push the repo → New Blueprint → pick `render.yaml`
2. Paste Google / Entra client credentials. Session secret is generated for you.
3. Add redirects:
   - `https://tenant-access-dashboard.onrender.com/auth/callback`
   - Google origin: `https://tenant-access-dashboard.onrender.com`

Fair warning on free: the web service sleeps, and free Postgres ages out after 30 days unless you upgrade.

### Grafana as a relying party

`render.yaml` also declares `tenant-access-grafana`: stock `grafana/grafana-oss` with generic OAuth pointed at the dashboard and the login form disabled, so SSO is the only way in.

1. In the dashboard → **Apps → New app**. Name `Grafana`, redirect URI `https://tenant-access-grafana.onrender.com/login/generic_oauth`, launch URL the same, pick a policy.
2. Copy the client id + secret into the Grafana service's `GF_AUTH_GENERIC_OAUTH_CLIENT_ID` / `_CLIENT_SECRET` env vars and redeploy.
3. Open Grafana → **Sign in with Tenant Access**. Role mapping is in the blueprint: `owner → Admin`, `admin → Editor`, `member → Viewer`.

### Outline as a relying party

Outline is a self-hosted Notion-like wiki. It needs **Postgres + Redis** (also in the blueprint), so it's heavier than Grafana on the free tier — fine for a demo; don't treat Outline's local file storage as durable (ephemeral disk).

1. **Apps → New app**. Name `Outline`, redirect URI `https://tenant-access-outline.onrender.com/auth/oidc.callback`, launch URL `https://tenant-access-outline.onrender.com`, pick a policy.
2. Paste client id / secret into Outline's `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` and redeploy.
3. Open Outline → **Continue with Tenant Access**.

Tokens include `preferred_username` (email) so Outline's default username claim works; we also set `OIDC_USERNAME_CLAIM=email` in the blueprint.

Locally, any OIDC client works against `http://localhost:8000` (issuer, discovery, JWKS).

### Fly.io

Render alone would be enough to run the app. Fly is here on purpose: **prove the Docker image is host-agnostic**. Blueprint/PaaS on Render, containers on Fly — if both work, the packaging is doing its job.

Live: https://tenant-access-dashboard.fly.dev

```powershell
# Windows install: iwr https://fly.io/install.ps1 -useb | iex
fly auth login
fly apps create tenant-access-dashboard
fly secrets set ENVIRONMENT=production `
  PUBLIC_BASE_URL=https://tenant-access-dashboard.fly.dev `
  SESSION_SECRET="<any long random string>" `
  DATABASE_URL="<external postgres url>" `
  GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... `
  ENTRA_CLIENT_ID=... ENTRA_CLIENT_SECRET=... ENTRA_TENANT_ID=common
fly deploy
```

I pointed Fly at Render's **external** `DATABASE_URL` so I didn't need a second database for the demo. Session secrets don't need to match across hosts — they only sign cookies for that domain.

Add the Fly callback in Google and Entra the same way:

- `https://tenant-access-dashboard.fly.dev/auth/callback`
- Google origin: `https://tenant-access-dashboard.fly.dev`

The app picks the redirect base from `RENDER_EXTERNAL_URL` or `PUBLIC_BASE_URL`.

### Infra as code

- **Live Render demo:** Blueprint (`render.yaml`).
- **Optional Terraform:** `infra/render/` — same web + Postgres shape if you prefer state over Blueprint. See [`infra/README.md`](infra/README.md).
- **Fly:** `fly.toml` + `flyctl` (Fly’s older TF provider isn’t something I’d hang a demo on).

### Ops & threat model

How I think about sessions, RLS, secrets, cold starts, and what’s still missing (e.g. login rate limits): [`docs/ops.md`](docs/ops.md).

---

## What I left out

I capped the scope so I could actually finish it. No fancy role hierarchy, no on-prem AD, no login rate limiting yet.

The OIDC provider is intentionally a subset: authorization code + PKCE with confidential clients, RS256, no refresh tokens, no dynamic client registration, no consent screen (the admin's access policy *is* the consent). Enough for real apps like Grafana; not a drop-in Keycloak.

What I *did* want in the repo: RLS isolation, Google + Entra, an audit trail (including failures, access/role changes and app sign-ins), owner vs promoted admin, disable/re-enable, **an OIDC provider with per-app access policies and live Grafana + Outline wired to it**, basic observability, EN/NO UI, **one portable image** on Render + Fly, a short ops write-up, and Terraform as an optional path next to the Blueprint.
