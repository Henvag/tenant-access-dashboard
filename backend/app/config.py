from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/access_dashboard"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/callback"
    session_secret: str = "change-me"
    frontend_origin: str = "http://localhost:5173"
    environment: str = "development"
    render_external_url: str = ""

    @field_validator("database_url")
    @classmethod
    def to_asyncpg(cls, value: str) -> str:
        url = value.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def public_origin(self) -> str:
        if self.is_production and self.render_external_url:
            return self.render_external_url.rstrip("/")
        return self.frontend_origin.rstrip("/")

    @property
    def resolved_redirect_uri(self) -> str:
        if self.is_production and self.render_external_url:
            return f"{self.public_origin}/auth/callback"
        return self.google_redirect_uri

    @property
    def cors_origins(self) -> list[str]:
        origins = {self.frontend_origin.rstrip("/"), self.public_origin}
        return [origin for origin in origins if origin]


settings = Settings()

STATIC_DIR = Path(__file__).resolve().parent / "static"
