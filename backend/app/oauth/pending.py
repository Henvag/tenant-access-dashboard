"""Session keys for an app sign-in parked while the person signs in to us.

/oauth/authorize parks its query string under PENDING_AUTHORIZE_KEY and the SAML
endpoints park {client_id, request id, RelayState} under PENDING_SAML_KEY.
/auth/callback and /oauth/resume pick up whichever is there. Only one is kept.
"""

PENDING_AUTHORIZE_KEY = "pending_authorize"
PENDING_SAML_KEY = "pending_saml"
PENDING_KEYS = (PENDING_AUTHORIZE_KEY, PENDING_SAML_KEY)


def resume_path(session: dict) -> str | None:
    """Where to send the browser to finish a parked app sign-in, if any."""
    if session.get(PENDING_SAML_KEY):
        return "/saml/continue"
    pending = session.get(PENDING_AUTHORIZE_KEY)
    if pending:
        return f"/oauth/authorize?{pending}"
    return None
