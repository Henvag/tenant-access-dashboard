"""OIDC provider tables: registered apps, per-user grants, auth codes, signing keys.

Everything holding secrets (clients, codes, grants) is tenant-scoped under FORCE RLS.
`oauth_client_lookup` is the one deliberate exception: a public client_id → tenant_id
index with no secrets, so the unauthenticated /oauth/token endpoint can discover which
tenant to scope the transaction to before touching the protected tables.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AccessPolicy(str, enum.Enum):
    everyone = "everyone"
    admins = "admins"
    assigned = "assigned"


class SigningKey(Base):
    """RS256 key pair used to sign ID/access tokens. Global, not tenant-scoped."""

    __tablename__ = "signing_keys"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    kid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    private_pem: Mapped[str] = mapped_column(Text, nullable=False)
    public_pem: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OAuthClient(Base):
    __tablename__ = "oauth_clients"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    client_secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    redirect_uris: Mapped[list[str]] = mapped_column(ARRAY(String(2048)), nullable=False)
    launch_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    access_policy: Mapped[AccessPolicy] = mapped_column(
        Enum(AccessPolicy, name="oauth_access_policy", create_constraint=False),
        nullable=False,
        default=AccessPolicy.everyone,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    grants: Mapped[list["AppGrant"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )

    @property
    def disabled(self) -> bool:
        return self.disabled_at is not None


class OAuthClientLookup(Base):
    """Public client_id → tenant_id index. Holds no secrets; intentionally not under RLS."""

    __tablename__ = "oauth_client_lookup"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )


class AppGrant(Base):
    __tablename__ = "app_grants"
    __table_args__ = (UniqueConstraint("client_pk", "user_id", name="uq_app_grants_client_user"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    client_pk: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("oauth_clients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    granted_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    client: Mapped["OAuthClient"] = relationship(back_populates="grants")


class PendingAppGrant(Base):
    """App access reserved for an email that has not signed in yet.

    Fulfilled into AppGrant on first matching login (same tenant + email).
    """

    __tablename__ = "pending_app_grants"
    __table_args__ = (
        UniqueConstraint("client_pk", "email", name="uq_pending_app_grants_client_email"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    client_pk: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("oauth_clients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    granted_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CompanyInviteToken(Base):
    """Public invite token → tenant. One active token per company; no secrets."""

    __tablename__ = "company_invite_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OAuthCode(Base):
    """Single-use authorization code. Stored hashed; expires after 60 seconds."""

    __tablename__ = "oauth_codes"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    client_pk: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("oauth_clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    code_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    scope: Mapped[str] = mapped_column(String(256), nullable=False)
    nonce: Mapped[str | None] = mapped_column(String(256), nullable=True)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    code_challenge_method: Mapped[str] = mapped_column(String(8), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
