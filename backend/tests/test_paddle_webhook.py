import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models.billing import CreditTransaction, PaddleEvent, SubscriptionPlan
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.services.paddle_service import verify_paddle_signature
from tests.fake_db import FakeDB

SECRET = "test-webhook-secret"


def _sign(body: bytes, secret: str = SECRET, ts: str = "1718000000") -> str:
    mac = hmac.new(
        secret.encode(), f"{ts}:{body.decode()}".encode(), hashlib.sha256
    ).hexdigest()
    return f"ts={ts};h1={mac}"


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setattr(settings, "PADDLE_WEBHOOK_SECRET", SECRET)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _user(**overrides) -> User:
    defaults = dict(
        email="seller@example.com",
        password_hash="x",
        credits_balance=30,
        subscription_tier="trial",
        subscription_status="trial",
    )
    defaults.update(overrides)
    return User(**defaults)


def _plans() -> list[SubscriptionPlan]:
    return [
        SubscriptionPlan(
            name="starter",
            display_name="Starter",
            price_monthly_usd=Decimal("19"),
            price_annual_usd=Decimal("182"),
            max_stores=1,
            credits_monthly=100,
            credits_rollover_pct=0,
            features={},
            paddle_price_id_monthly="pri_starter_m",
            is_active=True,
        ),
        SubscriptionPlan(
            name="growth",
            display_name="Growth",
            price_monthly_usd=Decimal("49"),
            price_annual_usd=Decimal("470"),
            max_stores=2,
            credits_monthly=300,
            credits_rollover_pct=50,
            features={},
            paddle_price_id_monthly="pri_growth_m",
            paddle_price_id_annual="pri_growth_a",
            is_active=True,
        ),
    ]


def _client(db: FakeDB) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _post(client: TestClient, payload: dict, signature: str | None = None):
    body = json.dumps(payload).encode()
    return client.post(
        "/webhooks/paddle",
        content=body,
        headers={"Paddle-Signature": signature or _sign(body)},
    )


def _created_payload(user: User, notification_id="ntf_1") -> dict:
    return {
        "notification_id": notification_id,
        "event_type": "subscription.created",
        "data": {
            "id": "sub_1",
            "customer_id": "ctm_1",
            "next_billed_at": "2026-07-12T00:00:00Z",
            "custom_data": {"user_id": str(user.id), "billing_period": "monthly"},
            "items": [{"price": {"id": "pri_growth_m"}}],
        },
    }


def test_signature_roundtrip():
    body = b'{"a":1}'
    assert verify_paddle_signature(body, _sign(body), SECRET) is True
    assert verify_paddle_signature(b'{"a":2}', _sign(body), SECRET) is False
    assert verify_paddle_signature(body, None, SECRET) is False
    assert verify_paddle_signature(body, _sign(body), "") is False


def test_webhook_rejects_bad_signature():
    client = _client(FakeDB())
    resp = _post(client, {"event_type": "subscription.created"}, signature="ts=1;h1=bad")
    assert resp.status_code == 401


def test_webhook_ignores_unhandled_events():
    client = _client(FakeDB())
    resp = _post(client, {"notification_id": "n1", "event_type": "address.created"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_subscription_created_activates_user_and_allocates_credits():
    user = _user()
    db = FakeDB(user, *_plans())
    client = _client(db)

    resp = _post(client, _created_payload(user))

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert user.subscription_status == "active"
    assert user.subscription_tier == "growth"
    assert user.billing_interval == "monthly"
    assert user.paddle_subscription_id == "sub_1"
    assert user.paddle_customer_id == "ctm_1"
    assert user.trial_ends_at is None
    assert user.subscription_current_period_end is not None
    assert user.credits_balance == 330  # 30 trial + 300 growth

    txn = db.query(CreditTransaction).first()
    assert txn.amount == 300
    assert txn.balance_after == 330
    assert txn.transaction_type == "subscription_renewal"

    event = db.query(PaddleEvent).first()
    assert event.paddle_event_id == "ntf_1"
    assert event.error_message is None
    assert str(event.user_id) == str(user.id)


def test_replayed_event_is_not_applied_twice():
    user = _user()
    db = FakeDB(user, *_plans())
    client = _client(db)

    _post(client, _created_payload(user))
    resp = _post(client, _created_payload(user))

    assert resp.json()["status"] == "already_processed"
    assert user.credits_balance == 330  # unchanged
    assert db.query(CreditTransaction).count() == 1


def test_topup_transaction_adds_credits():
    user = _user()
    db = FakeDB(user, *_plans())
    client = _client(db)

    resp = _post(
        client,
        {
            "notification_id": "ntf_topup",
            "event_type": "transaction.completed",
            "data": {
                "id": "txn_1",
                "custom_data": {
                    "user_id": str(user.id),
                    "transaction_type": "credit_topup",
                    "credits": 150,
                },
                "items": [{"price": {"id": "pri_topup_150"}}],
            },
        },
    )

    assert resp.json()["status"] == "ok"
    assert user.credits_balance == 180
    txn = db.query(CreditTransaction).first()
    assert txn.transaction_type == "topup_purchase"
    assert txn.paddle_transaction_id == "txn_1"


def test_renewal_transaction_allocates_monthly_credits():
    user = _user(
        subscription_tier="growth",
        subscription_status="past_due",
        paddle_subscription_id="sub_1",
    )
    db = FakeDB(user, *_plans())
    client = _client(db)

    resp = _post(
        client,
        {
            "notification_id": "ntf_renew",
            "event_type": "transaction.completed",
            "data": {
                "id": "txn_2",
                "origin": "subscription_recurring",
                "subscription_id": "sub_1",
            },
        },
    )

    assert resp.json()["status"] == "ok"
    assert user.credits_balance == 330
    assert user.subscription_status == "active"


def test_first_payment_transaction_does_not_double_allocate():
    user = _user(subscription_tier="growth", paddle_subscription_id="sub_1")
    db = FakeDB(user, *_plans())
    client = _client(db)

    resp = _post(
        client,
        {
            "notification_id": "ntf_first",
            "event_type": "transaction.completed",
            "data": {"id": "txn_3", "origin": "web", "subscription_id": "sub_1"},
        },
    )

    assert resp.json()["status"] == "ok"
    assert user.credits_balance == 30  # created-event grants, not this one


def test_upgrade_tops_up_credit_difference():
    user = _user(
        subscription_tier="starter",
        subscription_status="active",
        paddle_subscription_id="sub_1",
    )
    db = FakeDB(user, *_plans())
    client = _client(db)

    resp = _post(
        client,
        {
            "notification_id": "ntf_upgrade",
            "event_type": "subscription.updated",
            "data": {
                "id": "sub_1",
                "next_billed_at": "2026-07-12T00:00:00Z",
                "items": [{"price": {"id": "pri_growth_m"}}],
            },
        },
    )

    assert resp.json()["status"] == "ok"
    assert user.subscription_tier == "growth"
    assert user.credits_balance == 230  # 30 + (300 - 100)


def test_cancellation_and_payment_failure_set_statuses():
    user = _user(subscription_status="active", paddle_subscription_id="sub_1")
    db = FakeDB(user, *_plans())
    client = _client(db)

    _post(
        client,
        {
            "notification_id": "ntf_fail",
            "event_type": "transaction.payment_failed",
            "data": {"subscription_id": "sub_1"},
        },
    )
    assert user.subscription_status == "past_due"

    _post(
        client,
        {
            "notification_id": "ntf_cancel",
            "event_type": "subscription.cancelled",
            "data": {"id": "sub_1"},
        },
    )
    assert user.subscription_status == "cancelling"
    assert user.subscription_cancelled_at is not None


def test_handler_failure_recorded_and_returns_500(monkeypatch):
    from app.services.paddle_service import PaddleWebhookService

    monkeypatch.setattr(
        PaddleWebhookService,
        "handle",
        lambda self, event_type, data: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    db = FakeDB()
    client = _client(db)

    resp = _post(
        client,
        {
            "notification_id": "ntf_err",
            "event_type": "subscription.created",
            "data": {},
        },
    )

    assert resp.status_code == 500
    event = db.query(PaddleEvent).first()
    assert event.paddle_event_id == "ntf_err"
    assert "boom" in event.error_message
