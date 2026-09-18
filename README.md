# Tenant Access Dashboard

Small multi-tenant SSO/access app: a company registers, people sign in with Google, an admin sees who has access **in their tenant only**.

Built as a working portfolio slice for identity/access work (multi-tenant SaaS, OIDC, Postgres RLS). Stack is FastAPI + React + Postgres — not .NET — so it can be shipped as a complete product. CI, Docker, and Render cover the DevOps side of that story.

**Live demo:** https://tenant-access-dashboard.onrender.com (free tier — first load can take ~30 s while the service wakes up)

## Screenshots

| Landing / sign-in | Admin overview |
| --- | --- |
| ![Landing page with Google sign-in and company registration](docs/screenshots/landing.png) | ![Admin overview with stat cards and recent sign-ins](docs/screenshots/overview.png) |

| People directory (admin) | Norwegian UI |
| --- | --- |
| ![People table with search, role filter and activity status](docs/screenshots/people.png) | ![Same dashboard with the language toggle set to Norwegian](docs/screenshots/norwegian.png) |

## Try it in 30 seconds

1. Open the live demo and pick **Register company**. Use your own email domain (`gmail.com` works for a personal account).
2. Click **Continue with Google** and sign in with an account on that domain. The first person from a domain becomes **admin**.
3. You land on the **Overview**: how many people, admins, members, and who signed in recently. **People** is the full directory with search and role filter.
4. Register a second company on a different domain and sign in with an account from it. That admin sees only their own tenant — the first one is invisible to them, enforced by Postgres row-level security, not just the UI.

## What it demonstrates

- **Multi-tenant isolation:** `tenant_id` on rows plus Postgres **row-level security** (`FORCE RLS`). CI runs as a non-superuser so RLS cannot be bypassed.
- **OIDC:** Google sign-in via Authlib. Email domain (or Workspace `hd`) binds the user to the tenant. First user on a domain is admin.
- **Containers + CI/CD:** Docker image, Compose, GitHub Actions (tests, frontend build, image build).
- **One hosting model:** Render (web + Postgres). Blueprint is `render.yaml`.

Local demo allows `gmail.com`. A real Workspace domain works the same way.

## Architecture

```
browser  →  FastAPI (API + built React UI)  →  PostgreSQL
                 Google OIDC
```

Production serves the UI from the API (same origin) so the session cookie is straightforward.

## Local (without Docker)

Postgres 16, database `access_dashboard`, Python 3.12.

```powershell
cd backend
copy .env.example .env   # then set GOOGLE_CLIENT_ID / SECRET
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

UI: http://localhost:5173  
API: http://localhost:8000

Google Cloud OAuth client (Web application):

- Origins: `http://localhost:5173`, `http://localhost:8000`
- Redirect: `http://localhost:8000/auth/callback`
- Add yourself as a test user on the consent screen

Order: register a company with your email domain (`gmail.com` for a personal account), then Continue with Google.

## Docker Compose

Uses Postgres on host port **5433** so it does not collide with an existing local Postgres.

```powershell
docker compose up --build
```

Open http://localhost:8000 (UI and API together). Google redirect URI must be `http://localhost:8000/auth/callback`.

## Tests

```powershell
cd backend
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/access_dashboard_test"
.\.venv\Scripts\pytest
```

`tests/test_rls.py` creates two tenants and asserts each can only see its own users.

## GitHub Actions

On every push: backend pytest against Postgres, frontend production build, Docker image build.

## Deploy on Render

1. Push this repo to GitHub.
2. Render → **New** → **Blueprint** → select the repo (`render.yaml`).
3. Postgres and the web service are both on Render's **free** plans. The database expires after **30 days** unless you upgrade. The web app sleeps after idle time.
4. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` when prompted.
5. After the first deploy, copy the public URL (`https://<service>.onrender.com`) into Google OAuth:
   - Authorized origin: that URL
   - Redirect: `https://<service>.onrender.com/auth/callback`

The app reads `RENDER_EXTERNAL_URL` in production, so you do not set the redirect in Render env unless you override it.

## Not in this repo (on purpose)

Terraform, extra clouds, Entra ID / Active Directory, and roles beyond admin/user. Those are the natural next slices for an eADM-style platform.
