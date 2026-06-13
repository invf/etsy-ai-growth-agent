import uuid

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from tests.fake_db import FakeDB


def _user() -> User:
    user = User(
        email="o@example.com",
        password_hash="x",
        subscription_tier="trial",
        subscription_status="trial",
        credits_balance=30,
        credits_reserved=0,
        onboarding_completed=False,
        onboarding_step=0,
    )
    user.id = uuid.uuid4()
    return user


def _client(db, user) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_onboarding_advances_step():
    user = _user()
    try:
        resp = _client(FakeDB(), user).post("/v1/auth/onboarding", json={"step": 2})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["onboarding_step"] == 2
    assert data["onboarding_completed"] is False
    assert user.onboarding_step == 2


def test_onboarding_marks_completed():
    user = _user()
    try:
        resp = _client(FakeDB(), user).post(
            "/v1/auth/onboarding", json={"step": 3, "completed": True}
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["data"]["onboarding_completed"] is True
    assert user.onboarding_completed is True


def test_onboarding_rejects_out_of_range_step():
    user = _user()
    try:
        resp = _client(FakeDB(), user).post("/v1/auth/onboarding", json={"step": 99})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422
