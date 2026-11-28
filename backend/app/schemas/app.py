from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import AccessPolicy


def _check_url(value: str) -> str:
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("must be an absolute http(s) URL")
    if parts.fragment:
        raise ValueError("must not contain a fragment")
    if len(value) > 2048:
        raise ValueError("too long")
    return value


class AppOut(BaseModel):
    id: UUID
    name: str
    client_id: str
    redirect_uris: list[str]
    launch_url: str | None
    backchannel_logout_uri: str | None = None
    # Sign-out connector (Grafana, Outline, Gitea). The key itself never leaves the server.
    signout_kind: str | None = None
    signout_base_url: str | None = None
    signout_key_hint: str | None = None
    # Account provisioning (Slack). The token itself never leaves the server.
    provision_kind: str | None = None
    provision_key_hint: str | None = None
    # "oidc" or "saml". For SAML apps, what the app sends and where we answer,
    # plus the values the admin pastes into the app.
    protocol: str = "oidc"
    saml_entity_id: str | None = None
    saml_acs_url: str | None = None
    saml_nameid: str | None = None
    saml_sso_url: str | None = None
    saml_issuer: str | None = None
    saml_metadata_url: str | None = None
    saml_certificate_url: str | None = None
    access_policy: AccessPolicy
    disabled: bool
    created_at: datetime
    grant_count: int


class AppCreatedOut(AppOut):
    # Only returned once, at creation or rotation.
    client_secret: str


class SecretOut(BaseModel):
    client_secret: str


def _clean_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("name is required")
    return value


def _clean_redirects(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    cleaned = [_check_url(v) for v in value]
    if len(set(cleaned)) != len(cleaned):
        raise ValueError("duplicate redirect URI")
    return cleaned


def _clean_launch(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return _check_url(value)


def _clean_logout(value: str | None) -> str | None:
    cleaned = _clean_launch(value)
    if cleaned is None:
        return None
    if not cleaned.startswith("https://"):
        raise ValueError("logout URL must be https")
    return cleaned


def _clean_entity_id(value: str | None) -> str | None:
    """SAML entity IDs are usually URLs but may be URNs (urn:amazon:webservices)."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > 2048 or any(ch.isspace() for ch in value):
        raise ValueError("must be a URL or URN without spaces")
    return value


def _clean_acs(value: str | None) -> str | None:
    cleaned = _clean_launch(value)
    if cleaned is None:
        return None
    host = urlsplit(cleaned).hostname or ""
    if not cleaned.startswith("https://") and host not in {"localhost", "127.0.0.1"}:
        raise ValueError("ACS URL must be https")
    return cleaned


SamlNameId = Literal["email", "persistent"]


class AppCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    # Empty for an app people don't sign in to through us, only get an account in (Slack).
    redirect_uris: list[str] = Field(default_factory=list, max_length=10)
    launch_url: str | None = None
    backchannel_logout_uri: str | None = None
    access_policy: AccessPolicy = AccessPolicy.everyone
    protocol: Literal["oidc", "saml"] = "oidc"
    saml_entity_id: str | None = None
    saml_acs_url: str | None = None
    saml_nameid: SamlNameId = "email"

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _clean_name(value) or ""

    @field_validator("saml_entity_id")
    @classmethod
    def _entity(cls, value: str | None) -> str | None:
        return _clean_entity_id(value)

    @field_validator("saml_acs_url")
    @classmethod
    def _acs(cls, value: str | None) -> str | None:
        return _clean_acs(value)

    @model_validator(mode="after")
    def _saml_fields(self) -> "AppCreate":
        if self.protocol == "saml":
            if not self.saml_entity_id or not self.saml_acs_url:
                raise ValueError("SAML apps need an entity ID and an ACS URL")
            if self.redirect_uris:
                raise ValueError("SAML apps have no redirect URIs")
        elif self.saml_entity_id or self.saml_acs_url:
            raise ValueError("entity ID and ACS URL are only for SAML apps")
        return self

    @field_validator("redirect_uris")
    @classmethod
    def _redirects(cls, value: list[str]) -> list[str]:
        return _clean_redirects(value) or []

    @field_validator("launch_url")
    @classmethod
    def _launch(cls, value: str | None) -> str | None:
        return _clean_launch(value)

    @field_validator("backchannel_logout_uri")
    @classmethod
    def _logout(cls, value: str | None) -> str | None:
        return _clean_logout(value)


class AppPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    redirect_uris: list[str] | None = Field(default=None, min_length=1, max_length=10)
    launch_url: str | None = None
    backchannel_logout_uri: str | None = None
    access_policy: AccessPolicy | None = None
    disabled: bool | None = None
    # SAML apps only.
    saml_entity_id: str | None = None
    saml_acs_url: str | None = None
    saml_nameid: SamlNameId | None = None
    # Distinguish "not sent" from "clear it".
    clear_launch_url: bool = False
    clear_backchannel_logout_uri: bool = False

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return _clean_name(value)

    @field_validator("redirect_uris")
    @classmethod
    def _redirects(cls, value: list[str] | None) -> list[str] | None:
        return _clean_redirects(value)

    @field_validator("launch_url")
    @classmethod
    def _launch(cls, value: str | None) -> str | None:
        return _clean_launch(value)

    @field_validator("backchannel_logout_uri")
    @classmethod
    def _logout(cls, value: str | None) -> str | None:
        return _clean_logout(value)

    @field_validator("saml_entity_id")
    @classmethod
    def _entity(cls, value: str | None) -> str | None:
        return _clean_entity_id(value)

    @field_validator("saml_acs_url")
    @classmethod
    def _acs(cls, value: str | None) -> str | None:
        return _clean_acs(value)


class GrantsIn(BaseModel):
    user_ids: list[UUID] = Field(default_factory=list, max_length=500)
    emails: list[str] = Field(default_factory=list, max_length=200)


class GrantsOut(BaseModel):
    user_ids: list[UUID]
    pending_emails: list[str]


class MyAppOut(BaseModel):
    id: UUID
    name: str
    launch_url: str | None
    access_policy: AccessPolicy


class SignoutIn(BaseModel):
    kind: Literal["grafana", "outline", "gitea"]
    base_url: str = Field(min_length=1, max_length=2048)
    # Grafana: "username:password" of a server admin. Outline: API key. Gitea: admin token.
    secret: str = Field(min_length=1, max_length=1000)


class ProvisionIn(BaseModel):
    kind: Literal["slack"]
    # Slack: a user token (xoxp-...) with the admin scope, from a Workspace Owner or Admin.
    token: str = Field(min_length=1, max_length=1000)


class AccountOut(BaseModel):
    email: str
    user_id: UUID | None
    status: str
    last_error: str | None
    synced_at: datetime | None
    queued: bool


class AccountsOut(BaseModel):
    accounts: list[AccountOut]
