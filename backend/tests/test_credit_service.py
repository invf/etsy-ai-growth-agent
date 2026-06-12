import uuid
from unittest.mock import MagicMock

from app.db.models.user import User
from app.services.credit_service import CREDITS_PER_OPERATION, CreditService


def _user(balance=10) -> User:
    user = User(email="u@example.com", password_hash="x", credits_balance=balance)
    user.id = uuid.uuid4()
    return user


def test_reserve_grants_when_lua_returns_one():
    redis = MagicMock()
    redis.eval.return_value = 1

    assert CreditService(redis).reserve("u1", 2, "r1", balance=10) is True

    args = redis.eval.call_args.args
    assert args[1] == 2  # two keys
    assert args[2] == "credits:reserved:u1"
    assert args[3] == "credits:run:r1"


def test_reserve_denies_when_lua_returns_zero():
    redis = MagicMock()
    redis.eval.return_value = 0

    assert CreditService(redis).reserve("u1", 2, "r1", balance=1) is False


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


def test_settle_uses_actual_cost_when_given():
    redis = MagicMock()
    redis.get.return_value = "2"
    user = _user(balance=10)

    cost = CreditService(redis).settle("r1", user, actual_cost=1)

    assert cost == 1
    assert user.credits_balance == 9


def test_settle_never_drives_balance_negative():
    redis = MagicMock()
    redis.get.return_value = "5"
    user = _user(balance=3)

    CreditService(redis).settle("r1", user)

    assert user.credits_balance == 0


def test_release_frees_hold_without_charging():
    redis = MagicMock()
    redis.get.return_value = "2"

    CreditService(redis).release("u1", "r1")

    redis.decrby.assert_called_once_with("credits:reserved:u1", 2)
    redis.delete.assert_called_once_with("credits:run:r1")


def test_release_noop_when_nothing_reserved():
    redis = MagicMock()
    redis.get.return_value = None

    CreditService(redis).release("u1", "r1")

    redis.decrby.assert_not_called()
    redis.delete.assert_called_once()


def test_seo_deep_analysis_costs_two_credits():
    assert CREDITS_PER_OPERATION["seo_analysis_deep"] == 2
