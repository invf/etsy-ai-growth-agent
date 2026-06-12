from decimal import Decimal

from fastapi.testclient import TestClient

from app.db.models.billing import SubscriptionPlan
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
