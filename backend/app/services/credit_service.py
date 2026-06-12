"""Redis-backed credit reservation with DB settlement.

Credits are reserved atomically in Redis while an AI run is in flight
(preventing concurrent overdraft), then settled against
users.credits_balance on completion or released on failure.
Reservations expire automatically so a crashed worker never locks
credits forever.
"""

from typing import cast

import redis

from app.core.config import settings
from app.db.models.user import User

RESERVATION_TTL_SECONDS = 600

# Credits consumed per operation (ai-agent-spec §6.4)
CREDITS_PER_OPERATION = {
    "daily_agent_run": 5,
    "seo_analysis_deep": 2,
    "seo_analysis_quick": 0,
    "content_generation": 1,
    "competitor_analysis": 2,
    "image_analysis": 1,
    "trend_report": 1,
    "weekly_report": 3,
    "monthly_plan": 5,
}

# KEYS[1] = credits:reserved:{user_id}, KEYS[2] = credits:run:{run_id}
# ARGV = amount, balance, ttl. Atomic check-and-reserve.
RESERVE_LUA = """
local reserved = tonumber(redis.call('GET', KEYS[1]) or '0')
local amount = tonumber(ARGV[1])
local balance = tonumber(ARGV[2])
if balance - reserved < amount then
    return 0
end
redis.call('INCRBY', KEYS[1], amount)
redis.call('EXPIRE', KEYS[1], ARGV[3])
redis.call('SET', KEYS[2], amount, 'EX', ARGV[3])
return 1
"""


class CreditService:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    @staticmethod
    def _reserved_key(user_id: str) -> str:
        return f"credits:reserved:{user_id}"

    @staticmethod
    def _run_key(run_id: str) -> str:
        return f"credits:run:{run_id}"

    def _get_int(self, key: str) -> int:
        return int(cast("str | None", self.redis.get(key)) or 0)

    def reserved(self, user_id: str) -> int:
        return self._get_int(self._reserved_key(user_id))

    def available(self, user_id: str, balance: int) -> int:
        return balance - self.reserved(user_id)

    def reserve(self, user_id: str, amount: int, run_id: str, balance: int) -> bool:
        """Atomically reserve credits; False when the balance can't cover it."""
        granted = self.redis.eval(
            RESERVE_LUA,
            2,
            self._reserved_key(user_id),
            self._run_key(run_id),
            str(amount),
            str(balance),
            str(RESERVATION_TTL_SECONDS),
        )
        return granted == 1

    def settle(self, run_id: str, user: User, actual_cost: int | None = None) -> int:
        """Deduct the run's cost from the user's balance and free the hold."""
        reserved = self._get_int(self._run_key(run_id))
        cost = reserved if actual_cost is None else actual_cost
        user.credits_balance = max(0, user.credits_balance - cost)
        self._release(str(user.id), run_id, reserved)
        return cost

    def release(self, user_id: str, run_id: str) -> None:
        """Free a reservation without charging (failed/cancelled runs)."""
        reserved = self._get_int(self._run_key(run_id))
        self._release(user_id, run_id, reserved)

    def _release(self, user_id: str, run_id: str, reserved: int) -> None:
        if reserved:
            self.redis.decrby(self._reserved_key(user_id), reserved)
        self.redis.delete(self._run_key(run_id))


_credit_service: CreditService | None = None


def get_credit_service() -> CreditService:
    global _credit_service
    if _credit_service is None:
        _credit_service = CreditService(
            redis.from_url(settings.REDIS_URL, decode_responses=True)
        )
    return _credit_service
