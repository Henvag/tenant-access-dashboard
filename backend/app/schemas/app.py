from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

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


class AppCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    redirect_uris: list[str] = Field(min_length=1, max_length=10)
    launch_url: str | None = None
    access_policy: AccessPolicy = AccessPolicy.everyone

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _clean_name(value) or ""

    @field_validator("redirect_uris")
    @classmethod
    def _redirects(cls, value: list[str]) -> list[str]:
        return _clean_redirects(value) or []

    @field_validator("launch_url")
    @classmethod
    def _launch(cls, value: str | None) -> str | None:
        return _clean_launch(value)


class AppPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    redirect_uris: list[str] | None = Field(default=None, min_length=1, max_length=10)
    launch_url: str | None = None
    access_policy: AccessPolicy | None = None
    disabled: bool | None = None
    # Distinguish "not sent" from "clear it" for launch_url.
    clear_launch_url: bool = False

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
