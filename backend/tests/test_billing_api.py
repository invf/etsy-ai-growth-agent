import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.db.models.billing import SubscriptionPlan
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from tests.fake_db import FakeDB


def _plan(name, monthly, active=True, **overrides):
    defaults = dict(
        name=name,
        display_name=name.title(),
        price_monthly_usd=Decimal(monthly),
        price_annual_usd=Decimal(monthly) * 10,
        max_stores=1,
        credits_monthly=100,
        credits_rollover_pct=0,
        listing_analysis_cap=20,
        features={"audience": False},
        is_active=active,
    )
    defaults.update(overrides)
    return SubscriptionPlan(**defaults)


def test_billing_plans_route_registered():
    paths = {route.path for route in app.routes}
    assert "/v1/billing/plans" in paths


def test_plans_returned_sorted_and_active_only():
    db = FakeDB(
        _plan("growth", 49, paddle_price_id_monthly="pri_growth_m"),
        _plan("starter", 19),
        _plan("agency", 299, active=False),
    )
    app.dependency_overrides[get_db] = lambda: db
    try:
        resp = TestClient(app).get("/v1/billing/plans")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    plans = resp.json()["data"]
    assert [p["name"] for p in plans] == ["starter", "growth"]
    assert plans[0]["price_monthly_usd"] == 19.0
    assert plans[1]["paddle_price_id_monthly"] == "pri_growth_m"
    assert plans[1]["features"] == {"audience": False}


def test_plans_endpoint_is_public():
    db = FakeDB()
    app.dependency_overrides[get_db] = lambda: db
    try:
        resp = TestClient(app).get("/v1/billing/plans")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["data"] == []


def _growth_user() -> User:
    user = User(
        email="u@example.com",
        password_hash="x",
        credits_balance=247,
        subscription_tier="growth",
        subscription_status="active",
        billing_interval="monthly",
        subscription_current_period_end=datetime(
            2026, 7, 10, tzinfo=timezone.utc
        ),
    )
    user.id = uuid.uuid4()
    return user


def _authed_client(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_subscription_endpoint_returns_plan_price(monkeypatch):
    user = _growth_user()
    db = FakeDB(_plan("growth", 49))
    try:
        resp = _authed_client(db, user).get("/v1/billing/subscription")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["subscription_tier"] == "growth"
    assert data["price_usd"] == 49.0
    assert data["current_period_end"].startswith("2026-07-10")


def test_credits_endpoint_computes_availability(monkeypatch):
    from app.api.routes import billing as billing_routes

    service = MagicMock()
    service.reserved.return_value = 5
    monkeypatch.setattr(billing_routes, "get_credit_service", lambda: service)

    user = _growth_user()
    db = FakeDB(_plan("growth", 49, credits_monthly=300, credits_rollover_pct=50))
    try:
        resp = _authed_client(db, user).get("/v1/billing/credits")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data == {
        "balance": 247,
        "reserved": 5,
        "available": 242,
        "monthly_allotment": 300,
        "next_renewal_date": "2026-07-10",
        "rollover_percent": 50,
        "estimated_balance_at_renewal": 421,  # int(242 * 0.5) + 300
    }
