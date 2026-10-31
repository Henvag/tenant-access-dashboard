"""Stored AI keys use DATA_ENCRYPTION_KEY, and old session-key values still decrypt."""

import pytest

from app.agents import secrets
from app.config import settings


def test_new_values_need_the_data_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "session_secret", "cookie-secret")
    monkeypatch.setattr(settings, "data_encryption_key", "data-key")
    token = secrets.encrypt_secret("sk-live-123")
    assert secrets.decrypt_secret(token) == "sk-live-123"

    # Rotating the cookie secret no longer destroys stored keys.
    monkeypatch.setattr(settings, "session_secret", "rotated-cookie-secret")
    assert secrets.decrypt_secret(token) == "sk-live-123"

    # The cookie secret alone can't read them.
    monkeypatch.setattr(settings, "data_encryption_key", "")
    with pytest.raises(ValueError):
        secrets.decrypt_secret(token)


def test_values_from_before_the_data_key_still_decrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "session_secret", "cookie-secret")
    monkeypatch.setattr(settings, "data_encryption_key", "")
    legacy = secrets.encrypt_secret("sk-old")

    monkeypatch.setattr(settings, "data_encryption_key", "data-key")
    assert secrets.decrypt_secret(legacy) == "sk-old"
