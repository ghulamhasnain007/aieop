import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app import models  # noqa: F401


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # keep the same in-memory DB across connections
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_register_login_and_me(client):
    reg = client.post("/api/auth/register", json={
        "name": "Ahmed", "email": "ahmed@example.com", "password": "secret123", "role": "developer",
    })
    assert reg.status_code == 200

    login = client.post("/api/auth/login", data={"username": "ahmed@example.com", "password": "secret123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert token

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ahmed@example.com"
    assert me.json()["role"] == "developer"


def test_duplicate_email_rejected(client):
    client.post("/api/auth/register", json={
        "name": "A", "email": "dup@example.com", "password": "pw", "role": "viewer",
    })
    resp = client.post("/api/auth/register", json={
        "name": "B", "email": "dup@example.com", "password": "pw2", "role": "viewer",
    })
    assert resp.status_code == 400


def test_wrong_password_rejected(client):
    client.post("/api/auth/register", json={
        "name": "Sara", "email": "sara@example.com", "password": "rightpass", "role": "viewer",
    })
    resp = client.post("/api/auth/login", data={"username": "sara@example.com", "password": "wrongpass"})
    assert resp.status_code == 401


def test_me_requires_a_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_invalid_role_on_register_rejected(client):
    resp = client.post("/api/auth/register", json={
        "name": "X", "email": "x@example.com", "password": "pw", "role": "not_a_real_role",
    })
    assert resp.status_code == 400


def test_dev_mode_header_still_works_for_role_gated_endpoints(client, monkeypatch):
    # X-User-Role dev bypass should still work for existing endpoints when
    # no bearer token is supplied and ENVIRONMENT=development (test default).
    resp = client.post(
        "/api/chat", json={"message": "hello there"}, headers={"X-User-Role": "viewer"},
    )
    assert resp.status_code == 200
