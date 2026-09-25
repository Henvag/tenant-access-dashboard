from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/access_dashboard"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/callback"
    entra_client_id: str = ""
    entra_client_secret: str = ""
    # common = work + personal; consumers = personal Microsoft accounts only
    entra_tenant_id: str = "common"
    session_secret: str = "change-me"
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
