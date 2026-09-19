# Tenant Access Dashboard

I wanted a small, finished project that shows how I think about multi-tenant SaaS: identity, isolation, and shipping the same app without locking it to one host.

**Idea:** a company registers. People sign in with Google or Microsoft. An admin can see who has access — and cannot see another company's people, even if the app code forgets a filter.

[![CI](https://github.com/Henvag/tenant-access-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/Henvag/tenant-access-dashboard/actions/workflows/ci.yml)

**Why both Render and Fly?** Not because I need two demos — because I wanted to show the app isn't married to one cloud. Same multi-stage `Dockerfile`, same migrations and OIDC config; Render is a PaaS blueprint (`render.yaml`), Fly is a container platform (`fly.toml` + `fly deploy`). If the image is portable, switching hosts is mostly secrets and a redirect URI.

| | URL | Role |
| --- | --- | --- |
| **Render** | https://tenant-access-dashboard.onrender.com | Primary demo / blueprint deploy. Free tier — cold start can take ~30 s |
| **Fly.io** | https://tenant-access-dashboard.fly.dev | Same image on a second hosting model |

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
3. **Overview** is stats + recent activity. **People** is the directory. **Audit** shows successful and failed sign-ins (which IdP, when, and why it failed if it did).
4. Register a second company on a different domain and sign in there. You should only see that tenant.

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

Roles are deliberately just `admin` and `user`. I kept the surface small on purpose.

## What I used

| | | Why I picked it |
| --- | --- | --- |
| API | FastAPI, SQLAlchemy 2 async, Alembic | Comfortable, typed, good async Postgres story |
| Auth | Authlib (Google + Entra ID) | One OIDC path for two IdPs |
| DB | PostgreSQL 16 + RLS | Isolation where I can't forget it |
| UI | React + TypeScript + Vite | Built into the API image — one origin, one cookie |
| Ship | Docker, GitHub Actions, Render + Fly | One image, two hosting models (PaaS vs containers) |
| Ops | JSON logs, request IDs, `/health` with a DB check | Something useful when the free tier misbehaves |

One container builds the frontend, copies it in, runs migrations on start, and serves everything.

## Layout

```
backend/
  app/
    api/         auth, tenants, users, audit
    auth/        identity, oidc, rls, audit
    models/      Tenant, User, AuditEvent
    config.py    public URL from RENDER_EXTERNAL_URL or PUBLIC_BASE_URL
  alembic/
  tests/
frontend/        EN/NO i18n, dashboard, landing
Dockerfile · docker-compose.yml · render.yaml · fly.toml
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

I care most that tenant A cannot see B's users or audit rows, and that no tenant context fails closed.

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

---

## What I left out

I capped the scope so I could actually finish it. No Terraform yet, no fancy role hierarchy, no on-prem AD.

What I *did* want in the repo: RLS isolation, Google + Entra, an audit trail (including failures), basic observability, EN/NO UI, and **one portable image** shown on two hosts — Render for the main demo, Fly to make the “same container, different platform” point explicit.
