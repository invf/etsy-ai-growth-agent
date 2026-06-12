import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.db.models.notification import Notification
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.services import notification_service
from app.services.credit_service import CreditService
from tests.fake_db import FakeDB, FakeRedis


def _user(balance=10, tier="starter", email_notifications=True) -> User:
    user = User(
        email="u@example.com",
        password_hash="x",
        credits_balance=balance,
        subscription_tier=tier,
        email_notifications=email_notifications,
    )
    user.id = uuid.uuid4()
    return user


def _patch_credits(monkeypatch) -> CreditService:
    service = CreditService(FakeRedis())
    monkeypatch.setattr(
        notification_service, "get_credit_service", lambda: service
    )
    return service


# --- check_and_notify_low_credits -------------------------------------


def test_low_balance_creates_notification_and_sends_email(monkeypatch):
    _patch_credits(monkeypatch)
    sent = []
    monkeypatch.setattr(
        notification_service.email_service,
        "send_email",
        lambda to, subject, html: sent.append((to, subject)) or True,
    )

    db = FakeDB()
    user = _user(balance=10, tier="starter")  # below the 20 threshold
    notification = notification_service.check_and_notify_low_credits(db, user)

    assert notification is not None
    assert notification.type == "low_credits"
    assert notification.data == {"available": 10, "threshold": 20}
    assert notification.email_sent is True
    assert db.objects[Notification] == [notification]
    assert sent == [("u@example.com", "Low credits: 10 remaining")]


def test_notifies_only_once_per_billing_cycle(monkeypatch):
    _patch_credits(monkeypatch)
    monkeypatch.setattr(
        notification_service.email_service, "send_email", lambda *a: True
    )

    db = FakeDB()
    user = _user(balance=10)
    first = notification_service.check_and_notify_low_credits(db, user)
    second = notification_service.check_and_notify_low_credits(db, user)

    assert first is not None
    assert second is None
    assert len(db.objects[Notification]) == 1


def test_no_notification_above_threshold(monkeypatch):
    _patch_credits(monkeypatch)

    db = FakeDB()
    user = _user(balance=50, tier="starter")  # threshold is 20

    assert notification_service.check_and_notify_low_credits(db, user) is None
    assert db.objects[Notification] == []


def test_email_skipped_when_user_disabled_emails(monkeypatch):
    _patch_credits(monkeypatch)
    monkeypatch.setattr(
        notification_service.email_service,
        "send_email",
        lambda *a: (_ for _ in ()).throw(AssertionError("should not send")),
    )

    db = FakeDB()
    user = _user(balance=10, email_notifications=False)
    notification = notification_service.check_and_notify_low_credits(db, user)
    db.flush()  # applies the email_sent column default

    assert notification is not None
    assert notification.email_sent is False


def test_threshold_respects_reserved_credits(monkeypatch):
    """Available (not raw balance) drives the threshold check."""
    credits = _patch_credits(monkeypatch)
    monkeypatch.setattr(
        notification_service.email_service, "send_email", lambda *a: True
    )

    db = FakeDB()
    user = _user(balance=25, tier="starter")
    credits.reserve(str(user.id), 10, "r1", balance=25, tier="starter")

    notification = notification_service.check_and_notify_low_credits(db, user)

    assert notification is not None
    assert notification.data["available"] == 15


# --- /v1/notifications API ---------------------------------------------


def _notification(user_id, title="t", is_read=False, created=None) -> Notification:
    n = Notification(
        user_id=user_id,
        type="low_credits",
        priority="high",
        title=title,
        message="m",
        is_read=is_read,
        created_at=created or datetime.now(timezone.utc),
    )
    n.id = uuid.uuid4()
    return n


def _authed_client(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_list_notifications_returns_own_unread_count():
    user = _user()
    other = _user()
    db = FakeDB(
        _notification(user.id, title="mine-unread"),
        _notification(user.id, title="mine-read", is_read=True),
        _notification(other.id, title="not-mine"),
    )
    try:
        resp = _authed_client(db, user).get("/v1/notifications")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert {n["title"] for n in body["data"]} == {"mine-unread", "mine-read"}
    assert body["meta"]["unread_count"] == 1


def test_list_notifications_unread_only_filter():
    user = _user()
    db = FakeDB(
        _notification(user.id, title="unread"),
        _notification(user.id, title="read", is_read=True),
    )
    try:
        resp = _authed_client(db, user).get("/v1/notifications?unread_only=true")
    finally:
        app.dependency_overrides.clear()

    assert [n["title"] for n in resp.json()["data"]] == ["unread"]


def test_mark_read_sets_flag_and_404s_for_foreign():
    user = _user()
    other = _user()
    mine = _notification(user.id)
    foreign = _notification(other.id)
    db = FakeDB(mine, foreign)
    client = _authed_client(db, user)
    try:
        ok = client.post(f"/v1/notifications/{mine.id}/read")
        missing = client.post(f"/v1/notifications/{foreign.id}/read")
    finally:
        app.dependency_overrides.clear()

    assert ok.status_code == 200
    assert ok.json()["data"]["is_read"] is True
    assert mine.read_at is not None
    assert missing.status_code == 404
