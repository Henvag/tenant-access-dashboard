import pytest

from app.auth.identity import LoginError, workspace_domain_from_claims
from app.domain import normalize_workspace_domain
from app.schemas.tenant import TenantCreate


def test_normalizes_gmail_and_googlemail():
    assert normalize_workspace_domain("Gmail.COM") == "gmail.com"
    assert normalize_workspace_domain("googlemail.com") == "gmail.com"


def test_normalizes_microsoft_consumer_aliases():
    assert normalize_workspace_domain("Hotmail.com") == "outlook.com"
    assert normalize_workspace_domain("live.com") == "outlook.com"


def test_rejects_urls():
    with pytest.raises(ValueError, match="domain_url"):
        normalize_workspace_domain("https://acme.com")


def test_rejects_invalid_domain():
    with pytest.raises(ValueError, match="domain_invalid"):
        normalize_workspace_domain("not a domain")


def test_claims_prefer_hosted_domain():
    assert workspace_domain_from_claims("ada@acme.com", "acme.com") == "acme.com"


def test_claims_reject_hd_mismatch():
    with pytest.raises(LoginError) as exc:
        workspace_domain_from_claims("ada@acme.com", "other.com")
    assert exc.value.code == "domain_mismatch"


def test_tenant_create_accepts_gmail():
    body = TenantCreate(name="Demo", workspace_domain="Gmail.com")
    assert body.workspace_domain == "gmail.com"
