"""Create, reactivate and deactivate people's accounts in apps when their access changes.

The rule is one line: a person should have an active account in the app while
they can open it in Tenant Access (access policy, grant, or a pending email
grant) and aren't disabled. Anything that can change the answer schedules the
person; the worker (``worker.py``) works out the answer again when it runs and
makes the app match. So a job can run twice, late, or after a newer change,
and still do the right thing.

We only touch accounts we manage: a row in ``app_accounts`` exists once the
person had access while provisioning was on. Accounts made by hand in the app
for people who never had access through us are left alone.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.secrets import decrypt_secret
from app.auth.audit import record_account_change
from app.demo import is_demo_tenant
from app.models import (
    AccessPolicy,
    AppAccount,
    AppGrant,
    IdentityProvider,
    OAuthClient,
    PendingAppGrant,
    ProvisionOutbox,
    User,
    UserRole,
)
from app.provisioning import scim

logger = logging.getLogger("app.provisioning")

# app_accounts.status
PENDING = "pending"
ACTIVE = "active"
DEACTIVATED = "deactivated"
NONE = "none"
FAILED = "failed"

# Audit actions
CREATED = "created"
REACTIVATED = "reactivated"
LINKED = "linked"
DEACTIVATED_ACTION = "deactivated"
FAILED_ACTION = "failed"

# Delay before attempt n+1 after attempt n failed and may work later. About 7 hours in all.
RETRY_DELAYS = (
    timedelta(seconds=30),
    timedelta(minutes=2),
    timedelta(minutes=10),
    timedelta(hours=1),
    timedelta(hours=6),
)
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1


def is_enabled(client: OAuthClient) -> bool:
    return bool(client.provision_kind and client.provision_secret)


def has_access(client: OAuthClient, user: User, granted: bool) -> bool:
    if user.disabled_at is not None:
        return False
    if client.access_policy == AccessPolicy.everyone:
        return True
    if client.access_policy == AccessPolicy.admins:
        return user.role == UserRole.admin
    return granted


async def _provisioned_clients(db: AsyncSession, tenant_id) -> list[OAuthClient]:
    clients = (
        await db.scalars(
            select(OAuthClient).where(
                OAuthClient.tenant_id == tenant_id, OAuthClient.provision_kind.is_not(None)
            )
        )
    ).all()
    return [c for c in clients if is_enabled(c)]


async def _enqueue(db: AsyncSession, account: AppAccount) -> None:
    now = datetime.now(UTC)
    account.attempts = 0
    await db.flush()
    await db.execute(
        insert(ProvisionOutbox)
        .values(account_id=account.id, tenant_id=account.tenant_id, next_attempt_at=now)
        .on_conflict_do_update(
            index_elements=[ProvisionOutbox.account_id], set_={"next_attempt_at": now}
        )
    )


async def _account(
    db: AsyncSession, client: OAuthClient, email: str, user_id, *, create: bool
) -> AppAccount | None:
    row = await db.scalar(
        select(AppAccount).where(AppAccount.client_pk == client.id, AppAccount.email == email)
    )
    if row is None and user_id is not None:
        row = await db.scalar(
            select(AppAccount).where(
                AppAccount.client_pk == client.id, AppAccount.user_id == user_id
            )
        )
    if row is not None:
        if user_id is not None:
            row.user_id = user_id
            row.email = email
        return row
    if not create:
        return None
    row = AppAccount(
        tenant_id=client.tenant_id,
        client_pk=client.id,
        user_id=user_id,
        email=email,
        status=PENDING,
        attempts=0,
    )
    db.add(row)
    await db.flush()
    return row


async def schedule_person(
    db: AsyncSession, user: User, clients: list[OAuthClient] | None = None
) -> None:
    """Queue a check of ``user``'s accounts. Call after the change is flushed. RLS must be set."""
    if is_demo_tenant(user.tenant_id):
        return
    if clients is None:
        clients = await _provisioned_clients(db, user.tenant_id)
    if not clients:
        return
    await db.flush()
    granted = set(
        (await db.scalars(select(AppGrant.client_pk).where(AppGrant.user_id == user.id))).all()
    )
    for client in clients:
        if not is_enabled(client):
            continue
        want = has_access(client, user, client.id in granted)
        row = await _account(db, client, user.email, user.id, create=want)
        if row is not None:
            await _enqueue(db, row)


async def schedule_email(db: AsyncSession, client: OAuthClient, email: str) -> None:
    """Queue a check after a pending (email) grant was added or removed."""
    if not is_enabled(client) or is_demo_tenant(client.tenant_id):
        return
    await db.flush()
    pending = await db.scalar(
        select(
            exists().where(PendingAppGrant.client_pk == client.id, PendingAppGrant.email == email)
        )
    )
    row = await _account(db, client, email, None, create=bool(pending))
    if row is not None:
        await _enqueue(db, row)


async def schedule_app(db: AsyncSession, client: OAuthClient) -> None:
    """Check everyone for one app: after connecting it, a policy change, or "Sync now"."""
    if not is_enabled(client) or is_demo_tenant(client.tenant_id):
        return
    for row in (
        await db.scalars(select(AppAccount).where(AppAccount.client_pk == client.id))
    ).all():
        await _enqueue(db, row)
    users = (await db.scalars(select(User).where(User.tenant_id == client.tenant_id))).all()
    for user in users:
        await schedule_person(db, user, [client])
    emails = (
        await db.scalars(
            select(PendingAppGrant.email).where(PendingAppGrant.client_pk == client.id)
        )
    ).all()
    for email in emails:
        await schedule_email(db, client, email)


async def forget_email(db: AsyncSession, tenant_id, email: str) -> None:
    """Deleting a person: drop their address. The account id is enough to deactivate."""
    for row in (
        await db.scalars(
            select(AppAccount).where(AppAccount.tenant_id == tenant_id, AppAccount.email == email)
        )
    ).all():
        row.email = ""
        await _enqueue(db, row)
    await db.flush()


# ---------- worker side ----------


def next_attempt_after(attempts: int, retry_after: float | None) -> datetime | None:
    """When to try again after ``attempts`` failed tries, or None to give up."""
    if attempts >= MAX_ATTEMPTS:
        return None
    delay = RETRY_DELAYS[attempts - 1]
    if retry_after is not None:
        delay = max(delay, timedelta(seconds=retry_after))
    return datetime.now(UTC) + delay


async def _wanted(db: AsyncSession, client: OAuthClient, account: AppAccount, user: User | None) -> bool:
    if user is not None:
        granted = await db.scalar(
            select(exists().where(AppGrant.client_pk == client.id, AppGrant.user_id == user.id))
        )
        return has_access(client, user, bool(granted))
    if not account.email:
        return False
    pending = await db.scalar(
        select(
            exists().where(
                PendingAppGrant.client_pk == client.id, PendingAppGrant.email == account.email
            )
        )
    )
    return bool(pending)


async def _make_active(http, account: AppAccount, person: scim.Person) -> str | None:
    remote = await scim.get_user(http, account.remote_id) if account.remote_id else None
    if remote is None:
        remote = await scim.find_by_email(http, person.email)
    if remote is None:
        remote = await scim.create_user(http, person)
        action = CREATED
    elif not remote.active:
        await scim.set_active(http, remote.id, True)
        action = REACTIVATED
    else:
        action = LINKED if account.remote_id != remote.id else None
    account.remote_id = remote.id
    account.status = ACTIVE
    return action


async def _make_inactive(http, account: AppAccount) -> str | None:
    if not account.remote_id:
        # We never made or found an account for them, so there is nothing of ours to stop.
        account.status = NONE
        return None
    remote = await scim.get_user(http, account.remote_id)
    if remote is None:
        account.status = NONE
        account.remote_id = None
        return None
    action = None
    if remote.active:
        await scim.set_active(http, remote.id, False)
        action = DEACTIVATED_ACTION
    account.status = DEACTIVATED
    return action


async def sync_account(db: AsyncSession, account: AppAccount) -> datetime | None:
    """Make the app match. Returns when to try again, or None when done. RLS must be set."""
    client = await db.get(OAuthClient, account.client_pk)
    if client is None or not is_enabled(client):
        return None
    user = await db.get(User, account.user_id) if account.user_id else None
    want = await _wanted(db, client, account, user)
    email = user.email if user is not None else account.email
    person = scim.Person(email=email, display_name=user.display_name if user else None)
    action: str | None = None
    error: scim.ScimError | None = None
    try:
        token = decrypt_secret(client.provision_secret or "")
    except ValueError:
        error = scim.ScimError("provision_key_unreadable")
    else:
        try:
            async with scim.client_for(client.provision_kind or "", token) as http:
                if want:
                    action = await _make_active(http, account, person)
                else:
                    action = await _make_inactive(http, account)
        except scim.ScimError as exc:
            error = exc
        except (KeyError, TypeError, ValueError) as exc:
            logger.info("provisioning %s got an odd answer: %s", client.client_id, exc)
            error = scim.ScimError("provision_app_error")

    now = datetime.now(UTC)
    account.synced_at = now
    if error is not None:
        account.attempts += 1
        account.last_error = error.code
        retry_at = (
            next_attempt_after(account.attempts, error.retry_after)
            if error.retry_after is not None
            else None
        )
        if retry_at is not None:
            return retry_at
        account.status = FAILED
        await _audit(db, client, account, user, FAILED_ACTION, error.code)
        return None

    account.last_error = None
    account.attempts = 0
    if action is not None:
        await _audit(db, client, account, user, action, None)
    if not want and user is None:
        # A removed email grant or a deleted person: nothing left to remember.
        await db.delete(account)
    return None


async def _audit(
    db: AsyncSession,
    client: OAuthClient,
    account: AppAccount,
    user: User | None,
    action: str,
    error_code: str | None,
) -> None:
    await record_account_change(
        db,
        tenant_id=account.tenant_id,
        email=user.email if user is not None else account.email,
        user_id=user.id if user is not None else None,
        # The column needs a value; for an email-only account there is no sign-in yet.
        idp=user.idp if user is not None else IdentityProvider.google,
        details={"app": client.name, "action": action, "kind": client.provision_kind},
        error_code=error_code,
    )
