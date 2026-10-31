import re

_DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


def normalize_workspace_domain(raw: str) -> str:
    domain = raw.strip().lower()
    if domain.startswith("@"):
        domain = domain[1:]
    if domain.startswith("http://") or domain.startswith("https://"):
        raise ValueError("domain_url")
    if "/" in domain or " " in domain:
        raise ValueError("domain_invalid")
    if not _DOMAIN_RE.match(domain):
        raise ValueError("domain_invalid")
    if domain == "googlemail.com":
        return "gmail.com"
    # Personal Microsoft account aliases → one demo domain.
    if domain in {"hotmail.com", "live.com", "msn.com"}:
        return "outlook.com"
    return domain


# Shared mailbox providers. Nobody owns these domains on behalf of a company,
# so each person on them gets a private workspace keyed by their full address.
CONSUMER_DOMAINS = frozenset(
    {
        "gmail.com",
        "outlook.com",
        "yahoo.com",
        "icloud.com",
        "me.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "gmx.com",
        "online.no",
    }
)

MAX_WORKSPACE_KEY = 253


def is_personal_workspace(workspace_key: str) -> bool:
    return "@" in workspace_key


def workspace_key_for_email(email: str) -> str:
    """Company domain for work email, the whole address for consumer mailboxes."""
    local, _, raw_domain = email.strip().lower().rpartition("@")
    if not local or not raw_domain:
        raise ValueError("email_invalid")
    domain = normalize_workspace_domain(raw_domain)
    if domain not in CONSUMER_DOMAINS:
        return domain
    key = f"{local}@{domain}"
    if len(key) > MAX_WORKSPACE_KEY:
        raise ValueError("email_too_long")
    return key
