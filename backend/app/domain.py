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
