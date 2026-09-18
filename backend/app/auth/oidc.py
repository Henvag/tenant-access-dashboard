from authlib.integrations.starlette_client import OAuth

from app.config import Settings

GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"

PROVIDERS = frozenset({"google", "microsoft"})


def entra_metadata_url(tenant: str) -> str:
    return (
        f"https://login.microsoftonline.com/{tenant}/v2.0/"
        ".well-known/openid-configuration"
    )


def create_oauth(settings: Settings) -> OAuth:
    oauth = OAuth()
    if settings.google_client_id and settings.google_client_secret:
        oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url=GOOGLE_METADATA_URL,
            client_kwargs={"scope": "openid email profile"},
        )
    if settings.entra_client_id and settings.entra_client_secret:
        oauth.register(
            name="microsoft",
            client_id=settings.entra_client_id,
            client_secret=settings.entra_client_secret,
            server_metadata_url=entra_metadata_url(settings.entra_tenant_id),
            client_kwargs={"scope": "openid email profile"},
        )
    return oauth


# Entra /common and /consumers return tokens whose `iss` is the real tenant GUID,
# not the authority alias. Callback passes claims_options that skip a fixed issuer list.
