from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/access_dashboard"
    # Owner connection used only by Alembic. DATABASE_URL must be a restricted
    # role (NOBYPASSRLS) in production so row-level security actually applies.
    # Empty = migrations reuse DATABASE_URL (local development).
    migration_database_url: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/callback"
    entra_client_id: str = ""
    entra_client_secret: str = ""
    # common = work + personal; consumers = personal Microsoft accounts only
    entra_tenant_id: str = "common"
    session_secret: str = "change-me"
    # Encrypts stored AI provider keys. Separate from SESSION_SECRET (see agents/secrets.py).
    data_encryption_key: str = ""
    # Sign-in cookie lifetime. Starlette's default is 14 days.
    session_max_age_seconds: int = 12 * 60 * 60
    frontend_origin: str = "http://localhost:5173"
    environment: str = "development"
    # Render sets RENDER_EXTERNAL_URL; on Fly (or others) set PUBLIC_BASE_URL.
    render_external_url: str = ""
    public_base_url: str = ""

    # Stripe (subscriptions + optional Vipps annual one-shot). Empty = billing UI demo-only.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_team_monthly: str = ""
    stripe_price_business_monthly: str = ""
    stripe_price_team_annual: str = ""
    stripe_price_business_annual: str = ""
    # Vipps via Stripe Checkout (payment mode only; not subscription). Requires preview access.
    stripe_vipps_enabled: bool = False

    # Public read-only sample company behind "Explore the live demo".
    demo_enabled: bool = True

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def to_asyncpg(cls, value: str) -> str:
        if not value:
            return value
        url = value.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # Hosted Postgres (Neon, Supabase, ...) hands out libpq-style URLs with
        # ?sslmode=require&channel_binding=require. asyncpg rejects both keywords,
        # so translate sslmode to asyncpg's `ssl` and drop channel_binding.
        parts = urlsplit(url)
        if parts.query:
            params = []
            for key, val in parse_qsl(parts.query, keep_blank_values=True):
                if key == "sslmode":
                    params.append(("ssl", val))
                elif key != "channel_binding":
                    params.append((key, val))
            url = urlunsplit(parts._replace(query=urlencode(params)))
        return url

    @property
    def migrations_url(self) -> str:
        return self.migration_database_url or self.database_url

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def public_origin(self) -> str:
        if self.is_production:
            base = (self.public_base_url or self.render_external_url).rstrip("/")
            if base:
                return base
        return self.frontend_origin.rstrip("/")

    @property
    def resolved_redirect_uri(self) -> str:
        if self.is_production and (self.public_base_url or self.render_external_url):
            return f"{self.public_origin}/auth/callback"
        return self.google_redirect_uri

    @property
    def cors_origins(self) -> list[str]:
        # Keep both the custom domain and the Render URL during a Cloudflare cutover.
        origins = {self.frontend_origin.rstrip("/"), self.public_origin}
        if self.is_production:
            if self.public_base_url:
                origins.add(self.public_base_url.rstrip("/"))
            if self.render_external_url:
                origins.add(self.render_external_url.rstrip("/"))
        return [origin for origin in origins if origin]


settings = Settings()

STATIC_DIR = Path(__file__).resolve().parent / "static"
