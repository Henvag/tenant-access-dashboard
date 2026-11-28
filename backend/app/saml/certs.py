"""The key pair and self-signed certificate we sign SAML responses with.

One global certificate, stored in Postgres (Render disks are ephemeral) and
cached in-process. Admins paste it into each app once, so it lives ten years
and does not rotate with the OpenID Connect keys in app/oauth/keys.py.

Load it before scoping the transaction to a tenant: creating it on first use
commits, and a commit ends the transaction-local RLS setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SamlCertificate

_VALIDITY = timedelta(days=3650)


@dataclass(frozen=True)
class SigningCert:
    private_pem: str
    certificate_pem: str

    @property
    def certificate_b64(self) -> str:
        """The certificate body without PEM armour, as metadata and Slack want it."""
        lines = self.certificate_pem.strip().splitlines()
        return "".join(line for line in lines if not line.startswith("-----"))


_cached: SigningCert | None = None


def _generate() -> SamlCertificate:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Tenant Access SAML")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + _VALIDITY)
        .sign(key, hashes.SHA256())
    )
    return SamlCertificate(
        private_pem=key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        certificate_pem=cert.public_bytes(serialization.Encoding.PEM).decode(),
    )


async def signing_cert(db: AsyncSession) -> SigningCert:
    global _cached
    if _cached is not None:
        return _cached
    row = await db.scalar(
        select(SamlCertificate)
        .where(SamlCertificate.retired_at.is_(None))
        .order_by(SamlCertificate.created_at.desc())
        .limit(1)
    )
    if row is None:
        row = _generate()
        db.add(row)
        await db.commit()
    _cached = SigningCert(private_pem=row.private_pem, certificate_pem=row.certificate_pem)
    return _cached


def reset_cache() -> None:
    """Test hook."""
    global _cached
    _cached = None
