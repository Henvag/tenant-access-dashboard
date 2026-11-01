import asyncio
from contextlib import asynccontextmanager, suppress
import hmac
import os
import re

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.apps import router as apps_router
from app.api.agents import router as agents_router
from app.api.ask import router as ask_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.company import router as company_router
from app.api.domains import router as domains_router
from app.api.invites import router as invites_router
from app.api.partners import router as partners_router
from app.api.oauth import router as oauth_router
from app.api.users import router as users_router
from app.api.webhooks import router as webhooks_router
from app.auth.oidc import create_oauth
from app.config import STATIC_DIR, settings
from app.db import SessionLocal, engine
from app.demo import enforce_demo_read_only
from app.health import database_reachable
from app.logging_config import configure_logging
from app.observability import RequestIdMiddleware
from app.rls_guard import ensure_rls_enforced
from app.security_headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(json_logs=settings.is_production)
    await ensure_rls_enforced(engine)
    app.state.oauth = create_oauth(settings)
    sender = None
    if settings.webhooks_worker_enabled:
        from app.webhooks.worker import run_forever

        sender = asyncio.create_task(run_forever(SessionLocal))
    yield
    if sender is not None:
        sender.cancel()
        with suppress(asyncio.CancelledError):
            await sender


app = FastAPI(
    title="Tenant Access Dashboard",
    lifespan=lifespan,
    # Applies to every route: a demo session can read but never write.
    dependencies=[Depends(enforce_demo_read_only)],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    max_age=settings.session_max_age_seconds,
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
app.include_router(users_router)
app.include_router(audit_router)
app.include_router(apps_router)
app.include_router(agents_router)
app.include_router(ask_router)
app.include_router(company_router)
app.include_router(domains_router)
app.include_router(webhooks_router)
app.include_router(invites_router)
app.include_router(partners_router)
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
    expected = f"Bearer {token}".encode()
    if not token or not hmac.compare_digest((authorization or "").encode(), expected):
        raise HTTPException(status_code=404, detail="Not found")
    # Outline needs owner rights on its own database, not the restricted app role.
    raw = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
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

    # no-cache stores the latest document and forces the next visit to
    # revalidate it. no-store left the previously cached index.html in place,
    # so sign-in kept opening that older shell.
    index_headers = {"Cache-Control": "no-cache, must-revalidate"}

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
