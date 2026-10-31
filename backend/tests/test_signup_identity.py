"""Sign-in only trusts verified emails, and companies are created by signing in.

Covers the account-takeover (unverified Microsoft email, auto-linking by email)
and domain-claiming (unauthenticated tenant creation, shared Gmail tenant) fixes.
"""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.identity import (
    MICROSOFT_CONSUMER_TENANT_ID,
    LoginError,
    google_verified_email,
    microsoft_verified_email,
    upsert_user_from_oidc,
)
from app.auth.rls import set_tenant_rls
from app.models import IdentityProvider, Tenant, User, UserRole

ORG_TID = "11111111-2222-3333-4444-555555555555"


def _ms_claims(tid: str, **extra) -> dict:
    return {"tid": tid, "iss": f"https://login.microsoftonline.com/{tid}/v2.0", "sub": "s", **extra}


# ---------- claim verification (no database) ----------


def test_google_requires_email_verified_true() -> None:
    assert google_verified_email({"email": "Ada@Acme.com", "email_verified": True}) == "ada@acme.com"
    assert google_verified_email({"email": "ada@acme.com"}) is None
    assert google_verified_email({"email": "ada@acme.com", "email_verified": False}) is None


def test_microsoft_work_account_needs_verified_domain() -> None:
    # The nOAuth case: a directory the attacker controls sets any email.
    assert microsoft_verified_email(_ms_claims(ORG_TID, email="ceo@victim.com")) is None
    assert (
        microsoft_verified_email(_ms_claims(ORG_TID, email="ceo@victim.com", xms_edov=False))
        is None
    )
    assert (
        microsoft_verified_email(_ms_claims(ORG_TID, email="Ceo@Victim.com", xms_edov=True))
        == "ceo@victim.com"
    )
    assert (
        microsoft_verified_email(_ms_claims(ORG_TID, email="ceo@victim.com", xms_edov="true"))
        == "ceo@victim.com"
    )


def test_microsoft_work_account_ignores_upn_fallback() -> None:
    claims = _ms_claims(ORG_TID, preferred_username="ceo@victim.com", xms_edov=True)
    assert microsoft_verified_email(claims) is None


def test_microsoft_personal_account_is_trusted() -> None:
    claims = _ms_claims(MICROSOFT_CONSUMER_TENANT_ID, preferred_username="Bob@Outlook.com")
    assert microsoft_verified_email(claims) == "bob@outlook.com"


def test_microsoft_rejects_issuer_that_does_not_match_tenant() -> None:
    claims = _ms_claims(MICROSOFT_CONSUMER_TENANT_ID, email="bob@outlook.com")
    claims["iss"] = f"https://login.microsoftonline.com/{ORG_TID}/v2.0"
    assert microsoft_verified_email(claims) is None


# ---------- sign-in creates tenants (database) ----------


async def _login(factory, email, *, idp=IdentityProvider.google, sub=None, company=None, hd=None):
    async with factory() as session:
        user = await upsert_user_from_oidc(
            session,
            email=email,
            idp=idp,
            oidc_sub=sub or f"sub-{uuid4().hex}",
            display_name=None,
            hosted_domain=hd,
            new_tenant_name=company,
        )
        await session.flush()
        tenant = await session.get(Tenant, user.tenant_id)
        result = (user.id, user.role, tenant.workspace_domain, tenant.owner_user_id, tenant.name)
        await session.commit()
        return result


@pytest.mark.asyncio
async def test_register_company_by_signing_in(
    app_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    domain = f"signup-{uuid4().hex[:8]}.com"

    with pytest.raises(LoginError) as exc:
        await _login(app_session_factory, f"ada@{domain}")
    assert exc.value.code == "no_tenant"

    user_id, role, key, owner_id, name = await _login(
        app_session_factory, f"ada@{domain}", company="Acme"
    )
    assert (role, key, owner_id, name) == (UserRole.admin, domain, user_id, "Acme")

    # A colleague on the same domain joins the existing company as a member,
    # even if they also clicked "Register company".
    _, role2, key2, owner2, name2 = await _login(
        app_session_factory, f"bob@{domain}", company="Other name"
    )
    assert (role2, key2, owner2, name2) == (UserRole.user, domain, user_id, "Acme")


@pytest.mark.asyncio
async def test_gmail_users_get_separate_private_workspaces(
    app_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ada = f"ada.{uuid4().hex[:8]}@gmail.com"
    bob = f"bob.{uuid4().hex[:8]}@gmail.com"

    ada_id, ada_role, ada_key, _, _ = await _login(app_session_factory, ada, company="Ada's")
    assert ada_role == UserRole.admin and ada_key == ada

    # Bob cannot wander into Ada's workspace by signing in with Gmail.
    with pytest.raises(LoginError) as exc:
        await _login(app_session_factory, bob)
    assert exc.value.code == "no_tenant"

    bob_id, bob_role, bob_key, _, _ = await _login(app_session_factory, bob, company="Bob's")
    assert bob_role == UserRole.admin and bob_key == bob and bob_id != ada_id


@pytest.mark.asyncio
async def test_existing_account_is_not_linked_to_another_provider_by_email(
    app_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    domain = f"link-{uuid4().hex[:8]}.com"
    owner_sub = f"google-{uuid4().hex}"
    owner_id, _, _, _, _ = await _login(
        app_session_factory, f"owner@{domain}", sub=owner_sub, company="Link Co"
    )

    with pytest.raises(LoginError) as exc:
        await _login(
            app_session_factory,
            f"owner@{domain}",
            idp=IdentityProvider.microsoft,
            sub=f"attacker-{uuid4().hex}",
        )
    assert exc.value.code == "identity_conflict"

    async with app_session_factory() as session:
        tenant = await session.scalar(select(Tenant).where(Tenant.workspace_domain == domain))
        await set_tenant_rls(session, tenant.id)
        owner = await session.get(User, owner_id)
        assert (owner.idp, owner.oidc_sub) == (IdentityProvider.google, owner_sub)
