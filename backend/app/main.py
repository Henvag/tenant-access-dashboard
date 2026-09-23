from contextlib import asynccontextmanager
import os
import re

from fastapi import FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.apps import router as apps_router
from app.api.agents import router as agents_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.company import router as company_router
from app.api.invites import router as invites_router
from app.api.oauth import router as oauth_router
from app.api.tenants import router as tenants_router
from app.api.users import router as users_router
from app.auth.oidc import create_oauth
from app.config import STATIC_DIR, settings
from app.health import database_reachable
from app.logging_config import configure_logging
from app.observability import RequestIdMiddleware
from app.security_headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(json_logs=settings.is_production)
    app.state.oauth = create_oauth(settings)
    yield


app = FastAPI(title="Tenant Access Dashboard", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=settings.is_production,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
# Outermost: assign/echo X-Request-ID and emit structured access logs.
app.add_middleware(RequestIdMiddleware)
app.include_router(auth_router)
app.include_router(tenants_router)
app.include_router(users_router)
app.include_router(audit_router)
app.include_router(apps_router)
app.include_router(agents_router)
app.include_router(company_router)
app.include_router(invites_router)
app.include_router(billing_router)
app.include_router(oauth_router)


@app.get("/health")
async def health(response: Response):
    """Liveness + DB readiness. Render uses this path as the health check."""
    db_ok = await database_reachable()
    body = {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "unavailable",
    }
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return body


@app.get("/internal/outline-database-url")
async def outline_database_url(authorization: str | None = Header(default=None)):
    """Token-gated helper so Outline can reuse dashboard Postgres credentials
    against a dedicated `outline` database (free tier = one Postgres instance)."""
    token = os.environ.get("OUTLINE_DB_BOOTSTRAP_TOKEN", "")
    if not token or authorization != f"Bearer {token}":
        raise HTTPException(status_code=404, detail="Not found")
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        raise HTTPException(status_code=503, detail="DATABASE_URL unset")
    rewritten = re.sub(r"/[^/?]+(\?|$)", r"/outline\1", raw, count=1)
    rewritten = rewritten.replace("postgresql+asyncpg://", "postgres://", 1)
    rewritten = rewritten.replace("postgresql://", "postgres://", 1)
    return PlainTextResponse(rewritten)


def _mount_frontend() -> None:
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        return

    assets = STATIC_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    # The document points at a hashed bundle. If the browser reuses an older
    # index.html after the IdP redirect, the shell is missing nav added since
    # that copy was cached. A reload then fetches the new document.
    index_headers = {"Cache-Control": "no-store"}

    @app.get("/")
    async def spa_root():
        return FileResponse(index, headers=index_headers)

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        candidate = (STATIC_DIR / full_path).resolve()
        try:
            candidate.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return FileResponse(index, headers=index_headers)
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index, headers=index_headers)


_mount_frontend()
