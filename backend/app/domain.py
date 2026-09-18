import re

_DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


def normalize_workspace_domain(raw: str) -> str:
    domain = raw.strip().lower()
    if domain.startswith("@"):
        domain = domain[1:]
    if domain.startswith("http://") or domain.startswith("https://"):
        raise ValueError("Enter a domain like acme.com, not a URL")
    if "/" in domain or " " in domain:
        raise ValueError("Invalid workspace domain")
    if not _DOMAIN_RE.match(domain):
        raise ValueError("Invalid workspace domain")
    if domain == "googlemail.com":
        return "gmail.com"
    return domain
