"""The Outline bootstrap endpoint only answers to the exact bearer token."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("OUTLINE_DB_BOOTSTRAP_TOKEN", "s3cret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://app:pw@db.example/neondb?sslmode=require")
    monkeypatch.setenv(
        "MIGRATION_DATABASE_URL", "postgresql://owner:pw@db.example/neondb?sslmode=require"
    )
    return TestClient(app)


def test_rejects_wrong_or_missing_token(client: TestClient) -> None:
    assert client.get("/internal/outline-database-url").status_code == 404
    bad = {"Authorization": "Bearer s3cre"}
    assert client.get("/internal/outline-database-url", headers=bad).status_code == 404


def test_returns_owner_url_for_outline_database(client: TestClient) -> None:
    ok = {"Authorization": "Bearer s3cret"}
    response = client.get("/internal/outline-database-url", headers=ok)
    assert response.status_code == 200
    assert response.text == "postgres://owner:pw@db.example/outline?sslmode=require"
