from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.tenants import router as tenants_router
from app.api.users import router as users_router
from app.auth.oidc import create_oauth
from app.config import STATIC_DIR, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
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
app.include_router(auth_router)
app.include_router(tenants_router)
app.include_router(users_router)
app.include_router(audit_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


def _mount_frontend() -> None:
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        return

    assets = STATIC_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    async def spa_root():
        return FileResponse(index)

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        candidate = (STATIC_DIR / full_path).resolve()
        try:
            candidate.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return FileResponse(index)
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


_mount_frontend()
