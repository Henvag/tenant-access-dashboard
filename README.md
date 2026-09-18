# Tenant Access Dashboard

**A company signs up. Employees sign in with Google. An admin sees who has access — and can never see another company's people.**

Small, finished, deployed. Built to show how I approach multi-tenant SaaS, identity (OIDC), and the DevOps that gets it into production.

[![CI](https://github.com/Henvag/tenant-access-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/Henvag/tenant-access-dashboard/actions/workflows/ci.yml)

**Live demo → https://tenant-access-dashboard.onrender.com**
*(free tier: first load can take ~30 s while the service wakes up)*

---

## In pictures

| Landing / sign-in | Admin overview |
| --- | --- |
| ![Landing page with Google sign-in and company registration](docs/screenshots/landing.png) | ![Admin overview with stat cards and recent sign-ins](docs/screenshots/overview.png) |

| People directory (admin) | Same dashboard in Norwegian |
| --- | --- |
| ![People table with search, role filter and activity status](docs/screenshots/people.png) | ![Dashboard with the language toggle set to Norwegian](docs/screenshots/norwegian.png) |

## Try it in 30 seconds

1. Open the demo, pick **Register company**, and enter your email domain (`gmail.com` works for a personal account).
2. **Continue with Google** with an account on that domain. The first person from a domain becomes **admin**.
3. You land on **Overview** (people, admins, members, recent sign-ins). **People** is the full directory with search and role filter.
4. Register a second company on a different domain and sign in from there. That admin sees **only** their tenant — the first one does not exist for them, and that is enforced by the database, not the UI.

---

## The interesting part: isolation you can't forget to apply

Most multi-tenant bugs are a missing `WHERE tenant_id = ?`. This project makes that bug impossible at the database layer with **PostgreSQL row-level security**:

```sql
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;   -- applies even to the table owner

CREATE POLICY users_tenant_isolation ON users
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
```

Every request that touches user data runs inside a transaction that first sets the tenant:

```python
await session.execute(
    text("SELECT set_config('app.tenant_id', :tenant_id, true)"),   # true = transaction-local
    {"tenant_id": str(tenant_id)},
)
```

What that buys you:

- A query with **no** tenant context returns **zero rows** and rejects inserts — it fails closed.
- A forgotten filter in application code cannot leak another tenant's rows.
- `tests/test_rls.py` creates two tenants and proves each sees only its own users. CI runs those tests as a **non-superuser** role, because superusers bypass RLS and would make the test meaningless.

## How sign-in maps to a tenant

```
Google (OIDC) ──id_token──▶ FastAPI ──▶ email domain / Workspace `hd` claim ──▶ tenant
```

1. Company registers with a **workspace domain** (`acme.com`).
2. User clicks *Continue with Google*. Authlib runs the OpenID Connect code flow — no hand-rolled OAuth.
3. The verified email domain (or the Workspace `hd` claim, which wins if present) is looked up in `tenants`. No tenant → clear error. Mismatch between `hd` and email → rejected.
4. User is upserted **inside** that tenant's RLS context. First user on a domain gets `admin`; everyone after gets `user`.
5. A signed, HTTP-only session cookie carries `user_id` + `tenant_id`. Every later request re-applies the RLS context from it.

Roles are deliberately just `admin` / `user`. Admins see the directory; users see their own profile.

## Stack

| Layer | Choice | Why |
| --- | --- | --- |
| API | **FastAPI** (Python 3.12), SQLAlchemy 2 async, Alembic | Fast to ship, typed, first-class async Postgres |
| Auth | **Authlib** OIDC against Google | Standards-based; swap-in point for Entra ID later |
| Data | **PostgreSQL 16** with RLS | Isolation enforced where it can't be bypassed |
| UI | **React 18** + TypeScript + Vite | Built and served from the API — one origin, one cookie |
| Ship | **Docker** (multi-stage), **GitHub Actions**, **Render** blueprint | Container in, URL out |

Production is a single container: the Dockerfile builds the React app, copies it into the FastAPI image, runs migrations on start, and serves API + UI from the same origin. The UI is bilingual (EN/NO) with no i18n dependency.

## Repository map

```
backend/
  app/
    api/         auth (OIDC login/callback/me/logout), tenants (signup), users (admin list)
    auth/        identity.py  domain→tenant resolution + user upsert
                 oidc.py      Authlib client
                 rls.py       set_config('app.tenant_id') per transaction
    models/      Tenant, User (SQLAlchemy)
    schemas/     Pydantic request/response models
    config.py    env-driven settings; derives redirect URI from RENDER_EXTERNAL_URL in prod
  alembic/       migrations, including the RLS policy
  tests/         domain parsing + two-tenant RLS isolation tests
frontend/
  src/           Landing, Dashboard, UserTable, i18n (EN/NO), design tokens in styles.css
.github/workflows/ci.yml   pytest (vs. Postgres, non-superuser) · frontend build · docker build
Dockerfile · docker-compose.yml · render.yaml
```

---

## Run it locally

### Option A: Docker Compose (simplest)

```powershell
docker compose up --build
```

Open http://localhost:8000. Postgres is exposed on host port **5433** so it won't collide with a local install.
Google redirect URI must be `http://localhost:8000/auth/callback`.

### Option B: Without Docker

Requires Postgres 16 with a database `access_dashboard`, Python 3.12, Node 22.

```powershell
cd backend
copy .env.example .env          # set GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm install
npm run dev                     # UI on http://localhost:5173, calls the API on :8000
```

### Google OAuth client (both options)

Create a *Web application* OAuth client in Google Cloud and set:

- Authorized origins: `http://localhost:5173`, `http://localhost:8000`
- Redirect URI: `http://localhost:8000/auth/callback`
- Add yourself as a test user on the consent screen

Then: register a company with your domain (`gmail.com` for a personal account) → *Continue with Google*.

## Tests

```powershell
cd backend
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/access_dashboard_test"
.\.venv\Scripts\pytest
```

The suite creates a dedicated test database and a non-superuser `app_test` role, runs migrations, then asserts:

- tenant A cannot read tenant B's users (and vice versa)
- with no tenant context, reads return nothing and inserts are rejected
- domain normalization and `hd`/email mismatch handling

## CI/CD

Every push runs three GitHub Actions jobs in parallel: **backend** (pytest against a Postgres 16 service), **frontend** (production build), **docker** (image build). Render redeploys `main` automatically from the blueprint.

## Deploy on Render

1. Fork/push to GitHub.
2. Render → **New → Blueprint** → pick the repo. `render.yaml` provisions a web service + Postgres, both on free plans.
3. Enter `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` when prompted. `SESSION_SECRET` is generated for you.
4. After the first deploy, add to your Google OAuth client:
   - Authorized origin: `https://<service>.onrender.com`
   - Redirect URI: `https://<service>.onrender.com/auth/callback`

The app derives its redirect URI from `RENDER_EXTERNAL_URL`, so there is nothing else to configure.

> Free-tier notes: the web service sleeps after inactivity (hence the slow first load) and the Postgres instance expires after 30 days unless upgraded.

---

## Scope, and what comes next

Kept deliberately small so it could be **finished**. Not in this repo, in rough order of what I'd add next:

- **Entra ID** as a second identity provider (same Authlib pattern, different discovery URL)
- Sign-in **audit log** per tenant, reusing the RLS pattern
- **Terraform** + a second hosting model (Fly.io or a Kubernetes target)
- Structured logging / request IDs and a deeper `/health`

Roles beyond `admin` / `user` are also out — the point was to nail isolation first.
