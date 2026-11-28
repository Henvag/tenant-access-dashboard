"""Read SAML AuthnRequests and build signed SAML Responses.

We are the identity provider. A cloud app (the service provider, e.g. Slack)
sends the browser to us with an AuthnRequest; we answer by posting a signed
Response to the app's registered ACS URL. Only the registered ACS URL is ever
used, whatever the request asks for, so request signatures are not needed.
"""

from __future__ import annotations

import base64
import binascii
import re
import secrets
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from lxml import etree
from signxml import XMLSigner

from app.saml.certs import SigningCert

NS_SAMLP = "urn:oasis:names:tc:SAML:2.0:protocol"
NS_SAML = "urn:oasis:names:tc:SAML:2.0:assertion"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"
NS_MD = "urn:oasis:names:tc:SAML:2.0:metadata"
NS_XS = "http://www.w3.org/2001/XMLSchema"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

BINDING_POST = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
BINDING_REDIRECT = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
NAMEID_EMAIL = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
NAMEID_PERSISTENT = "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"
NAMEID_FORMATS = {"email": NAMEID_EMAIL, "persistent": NAMEID_PERSISTENT}

EXC_C14N = "http://www.w3.org/2001/10/xml-exc-c14n#"
# How long the app may take to accept the response, and clock skew we allow for.
RESPONSE_TTL = timedelta(minutes=5)
CLOCK_SKEW = timedelta(minutes=2)
SESSION_TTL = timedelta(hours=8)

_MAX_REQUEST_BYTES = 64 * 1024
# SAML IDs are xs:ID (an NCName). Anything else is not echoed back.
_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]{0,255}$")

_PARSER = etree.XMLParser(
    resolve_entities=False, no_network=True, huge_tree=False, remove_comments=True
)


class SamlError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AuthnRequest:
    id: str | None
    issuer: str | None
    acs_url: str | None
    protocol_binding: str | None


def decode_request(raw: str, *, deflated: bool) -> bytes:
    """Base64 (and for the Redirect binding, raw DEFLATE) decode a SAMLRequest."""
    try:
        data = base64.b64decode(raw, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise SamlError("saml_bad_request") from exc
    if deflated:
        try:
            inflater = zlib.decompressobj(-15)
            data = inflater.decompress(data, _MAX_REQUEST_BYTES)
            if inflater.unconsumed_tail:
                raise SamlError("saml_bad_request")
        except zlib.error as exc:
            raise SamlError("saml_bad_request") from exc
    if len(data) > _MAX_REQUEST_BYTES:
        raise SamlError("saml_bad_request")
    return data


def encode_redirect(xml: bytes) -> str:
    """Encode a request the way the HTTP-Redirect binding carries it."""
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(compressor.compress(xml) + compressor.flush()).decode()


def parse_authn_request(xml: bytes) -> AuthnRequest:
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        raise SamlError("saml_bad_request")
    try:
        root = etree.fromstring(xml, parser=_PARSER)
    except etree.XMLSyntaxError as exc:
        raise SamlError("saml_bad_request") from exc
    if root.tag != f"{{{NS_SAMLP}}}AuthnRequest":
        raise SamlError("saml_bad_request")
    request_id = root.get("ID")
    if request_id is not None and not _ID_RE.match(request_id):
        raise SamlError("saml_bad_request")
    issuer_el = root.find(f"{{{NS_SAML}}}Issuer")
    issuer = (issuer_el.text or "").strip() if issuer_el is not None else None
    return AuthnRequest(
        id=request_id,
        issuer=issuer or None,
        acs_url=root.get("AssertionConsumerServiceURL"),
        protocol_binding=root.get("ProtocolBinding"),
    )


def _id() -> str:
    return "_" + secrets.token_hex(20)


def _instant(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _el(parent, ns: str, tag: str, text: str | None = None, **attrs: str):
    el = etree.SubElement(parent, f"{{{ns}}}{tag}")
    for key, value in attrs.items():
        el.set(key, value)
    if text is not None:
        el.text = text
    return el


def _signer() -> XMLSigner:
    signer = XMLSigner(c14n_algorithm=EXC_C14N)
    signer.namespaces = {"ds": NS_DS}
    return signer


def _placeholder(parent, index: int) -> None:
    sig = etree.Element(f"{{{NS_DS}}}Signature", nsmap={"ds": NS_DS})
    sig.set("Id", "placeholder")
    parent.insert(index, sig)


def split_name(display_name: str | None, email: str) -> tuple[str, str]:
    name = (display_name or "").strip()
    if not name:
        return email.split("@")[0], ""
    first, _, last = name.rpartition(" ")
    return (first, last) if first else (last, "")


def build_response(
    *,
    cert: SigningCert,
    issuer: str,
    audience: str,
    acs_url: str,
    in_response_to: str | None,
    nameid_format: str,
    nameid: str,
    attributes: dict[str, str],
    now: datetime | None = None,
) -> bytes:
    """A Response with a signed Assertion, and the Response signed too.

    Slack, Zoom and most apps accept either; signing both satisfies apps that
    insist on one or the other.
    """
    now = now or datetime.now(UTC)
    not_after = _instant(now + RESPONSE_TTL)
    response_id, assertion_id = _id(), _id()

    assertion = etree.Element(
        f"{{{NS_SAML}}}Assertion",
        nsmap={"saml": NS_SAML, "xs": NS_XS, "xsi": NS_XSI},
    )
    assertion.set("ID", assertion_id)
    assertion.set("Version", "2.0")
    assertion.set("IssueInstant", _instant(now))
    _el(assertion, NS_SAML, "Issuer", issuer)
    subject = _el(assertion, NS_SAML, "Subject")
    _el(subject, NS_SAML, "NameID", nameid, Format=nameid_format, SPNameQualifier=audience)
    confirmation = _el(
        subject, NS_SAML, "SubjectConfirmation", Method="urn:oasis:names:tc:SAML:2.0:cm:bearer"
    )
    data = _el(confirmation, NS_SAML, "SubjectConfirmationData", NotOnOrAfter=not_after)
    data.set("Recipient", acs_url)
    if in_response_to:
        data.set("InResponseTo", in_response_to)
    conditions = _el(
        assertion,
        NS_SAML,
        "Conditions",
        NotBefore=_instant(now - CLOCK_SKEW),
        NotOnOrAfter=not_after,
    )
    restriction = _el(conditions, NS_SAML, "AudienceRestriction")
    _el(restriction, NS_SAML, "Audience", audience)
    authn = _el(
        assertion,
        NS_SAML,
        "AuthnStatement",
        AuthnInstant=_instant(now),
        SessionIndex=_id(),
        SessionNotOnOrAfter=_instant(now + SESSION_TTL),
    )
    context = _el(authn, NS_SAML, "AuthnContext")
    _el(
        context,
        NS_SAML,
        "AuthnContextClassRef",
        "urn:oasis:names:tc:SAML:2.0:ac:classes:unspecified",
    )
    if attributes:
        statement = _el(assertion, NS_SAML, "AttributeStatement")
        for name, value in attributes.items():
            attr = _el(
                statement,
                NS_SAML,
                "Attribute",
                Name=name,
                NameFormat="urn:oasis:names:tc:SAML:2.0:attrname-format:basic",
            )
            av = _el(attr, NS_SAML, "AttributeValue", value)
            av.set(f"{{{NS_XSI}}}type", "xs:string")

    # The Signature goes right after Issuer, as the schema requires.
    _placeholder(assertion, 1)
    signed_assertion = _signer().sign(
        assertion,
        key=cert.private_pem,
        cert=cert.certificate_pem,
        reference_uri=assertion_id,
        id_attribute="ID",
    )

    response = etree.Element(
        f"{{{NS_SAMLP}}}Response", nsmap={"samlp": NS_SAMLP, "saml": NS_SAML}
    )
    response.set("ID", response_id)
    response.set("Version", "2.0")
    response.set("IssueInstant", _instant(now))
    response.set("Destination", acs_url)
    if in_response_to:
        response.set("InResponseTo", in_response_to)
    _el(response, NS_SAML, "Issuer", issuer)
    status = _el(response, NS_SAMLP, "Status")
    _el(status, NS_SAMLP, "StatusCode", Value="urn:oasis:names:tc:SAML:2.0:status:Success")
    response.append(signed_assertion)
    _placeholder(response, 1)
    signed = _signer().sign(
        response,
        key=cert.private_pem,
        cert=cert.certificate_pem,
        reference_uri=response_id,
        id_attribute="ID",
    )
    return etree.tostring(signed, xml_declaration=False, encoding="utf-8")


def idp_metadata(*, cert: SigningCert, entity_id: str, sso_url: str) -> bytes:
    root = etree.Element(
        f"{{{NS_MD}}}EntityDescriptor", nsmap={"md": NS_MD, "ds": NS_DS}
    )
    root.set("entityID", entity_id)
    idp = _el(
        root,
        NS_MD,
        "IDPSSODescriptor",
        WantAuthnRequestsSigned="false",
        protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol",
    )
    key = _el(idp, NS_MD, "KeyDescriptor", use="signing")
    info = _el(key, NS_DS, "KeyInfo")
    x509 = _el(info, NS_DS, "X509Data")
    _el(x509, NS_DS, "X509Certificate", cert.certificate_b64)
    for fmt in (NAMEID_EMAIL, NAMEID_PERSISTENT):
        _el(idp, NS_MD, "NameIDFormat", fmt)
    _el(idp, NS_MD, "SingleSignOnService", Binding=BINDING_POST, Location=sso_url)
    _el(idp, NS_MD, "SingleSignOnService", Binding=BINDING_REDIRECT, Location=sso_url)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")
