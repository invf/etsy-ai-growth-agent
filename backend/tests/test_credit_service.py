import uuid
from unittest.mock import MagicMock

from app.db.models.user import User
from app.services.credit_service import (
    CREDITS_PER_OPERATION,
    DAILY_CREDIT_CAP,
    CreditService,
)
from tests.fake_db import FakeRedis


def _user(balance=10) -> User:
    user = User(email="u@example.com", password_hash="x", credits_balance=balance)
    user.id = uuid.uuid4()
    return user


def _service() -> CreditService:
    return CreditService(FakeRedis())


def test_reserve_grants_within_balance_and_cap():
    service = _service()

    assert service.reserve("u1", 2, "r1", balance=10, tier="starter") == "ok"
    assert service.reserved("u1") == 2
    assert service.daily_used("u1") == 2


def test_reserve_denies_when_balance_short():
    service = _service()

    result = service.reserve("u1", 2, "r1", balance=1, tier="starter")

    assert result == "insufficient_balance"
    assert service.reserved("u1") == 0
    assert service.daily_used("u1") == 0


def test_reserve_denies_when_daily_cap_hit():
    service = _service()  # trial cap = 10

    assert service.reserve("u1", 5, "r1", balance=100, tier="trial") == "ok"
    assert service.reserve("u1", 5, "r2", balance=100, tier="trial") == "ok"
    result = service.reserve("u1", 5, "r3", balance=100, tier="trial")

    assert result == "daily_cap_exceeded"
    assert service.daily_used("u1") == 10


def test_daily_cap_counts_settled_spend():
    """Settled (actually burned) credits stay in the daily counter."""
    service = _service()
    user = _user(balance=100)
    uid = str(user.id)

    assert service.reserve(uid, 5, "r1", balance=100, tier="trial") == "ok"
    service.settle("r1", user)
    assert service.reserve(uid, 5, "r2", balance=95, tier="trial") == "ok"
    service.settle("r2", user)

    assert service.daily_used(uid) == 10
    assert service.reserve(uid, 5, "r3", balance=90, tier="trial") == "daily_cap_exceeded"


def test_release_refunds_daily_counter():
    """A failed run must not consume daily allowance."""
    service = _service()

    service.reserve("u1", 5, "r1", balance=100, tier="trial")
    service.release("u1", "r1")

    assert service.daily_used("u1") == 0
    assert service.reserve("u1", 5, "r2", balance=100, tier="trial") == "ok"


def test_settle_with_cheaper_actual_cost_refunds_difference():
    service = _service()
    user = _user(balance=100)
    uid = str(user.id)

    service.reserve(uid, 5, "r1", balance=100, tier="trial")
    cost = service.settle("r1", user, actual_cost=2)

    assert cost == 2
    assert user.credits_balance == 98
    assert service.daily_used(uid) == 2


def test_unknown_tier_falls_back_to_trial_cap():
    assert CreditService.daily_cap("nonexistent") == DAILY_CREDIT_CAP["trial"]


def test_available_subtracts_reserved():
    redis = MagicMock()
    redis.get.return_value = "3"

    assert CreditService(redis).available("u1", balance=10) == 7


def test_settle_deducts_reserved_amount_and_frees_hold():
    redis = MagicMock()
    redis.get.return_value = "2"
    user = _user(balance=10)

    cost = CreditService(redis).settle("r1", user)

    assert cost == 2
    assert user.credits_balance == 8
    redis.decrby.assert_called_once_with(f"credits:reserved:{user.id}", 2)
    redis.delete.assert_called_once_with("credits:run:r1")


def test_settle_never_drives_balance_negative():
    redis = MagicMock()
    redis.get.return_value = "5"
    user = _user(balance=3)

    CreditService(redis).settle("r1", user)

    assert user.credits_balance == 0


def test_release_noop_when_nothing_reserved():
    redis = MagicMock()
    redis.get.return_value = None

    CreditService(redis).release("u1", "r1")

    redis.decrby.assert_not_called()
    redis.delete.assert_called_once()


def test_seo_deep_analysis_costs_two_credits():
    assert CREDITS_PER_OPERATION["seo_analysis_deep"] == 2


def test_starter_daily_cap_is_thirty():
    assert DAILY_CREDIT_CAP["starter"] == 30
