"""Redis-backed credit reservation with DB settlement.

Credits are reserved atomically in Redis while an AI run is in flight
(preventing concurrent overdraft), then settled against
users.credits_balance on completion or released on failure.
Reservations expire automatically so a crashed worker never locks
credits forever.

A per-tier daily cap (monetization-spec §2.2) is enforced inside the
same atomic reserve: a runaway agent loop can never burn more than the
tier's daily allowance, regardless of balance.
"""

from datetime import datetime, timezone
from typing import Literal, cast

import redis

from app.core.config import settings
from app.db.models.user import User

RESERVATION_TTL_SECONDS = 600
DAILY_COUNTER_TTL_SECONDS = 48 * 3600

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

# Hard daily credit cap per tier (monetization-spec §2.2) —
# prevents burning a monthly allotment in days via runaway loops
DAILY_CREDIT_CAP = {
    "trial": 10,
    "starter": 30,
    "growth": 60,
    "pro": 150,
    "agency": 500,
}

ReserveResult = Literal["ok", "insufficient_balance", "daily_cap_exceeded"]

# KEYS[1] = credits:reserved:{user_id}, KEYS[2] = credits:run:{run_id},
# KEYS[3] = credits:daily:{user_id}:{date}
# ARGV = amount, balance, reservation_ttl, daily_cap, daily_ttl.
# Atomic check-and-reserve: 1 = granted, 0 = balance short, -1 = daily cap hit.
RESERVE_LUA = """
local reserved = tonumber(redis.call('GET', KEYS[1]) or '0')
local daily_used = tonumber(redis.call('GET', KEYS[3]) or '0')
local amount = tonumber(ARGV[1])
local balance = tonumber(ARGV[2])
local daily_cap = tonumber(ARGV[4])
if balance - reserved < amount then
    return 0
end
if daily_used + amount > daily_cap then
    return -1
end
redis.call('INCRBY', KEYS[1], amount)
redis.call('EXPIRE', KEYS[1], ARGV[3])
redis.call('INCRBY', KEYS[3], amount)
redis.call('EXPIRE', KEYS[3], ARGV[5])
redis.call('SET', KEYS[2], amount, 'EX', ARGV[3])
return 1
"""

# Refund a counter without letting it go negative (the daily key may
# have expired between reserve and release).
DECR_FLOOR_LUA = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local amount = tonumber(ARGV[1])
if current > 0 then
    redis.call('DECRBY', KEYS[1], math.min(current, amount))
end
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

    @staticmethod
    def _daily_key(user_id: str) -> str:
        today = datetime.now(timezone.utc).date().isoformat()
        return f"credits:daily:{user_id}:{today}"

    def _get_int(self, key: str) -> int:
        return int(cast("str | None", self.redis.get(key)) or 0)

    def reserved(self, user_id: str) -> int:
        return self._get_int(self._reserved_key(user_id))

    def available(self, user_id: str, balance: int) -> int:
        return balance - self.reserved(user_id)

    def daily_used(self, user_id: str) -> int:
        return self._get_int(self._daily_key(user_id))

    @staticmethod
    def daily_cap(tier: str) -> int:
        return DAILY_CREDIT_CAP.get(tier, DAILY_CREDIT_CAP["trial"])

    def reserve(
        self, user_id: str, amount: int, run_id: str, balance: int, tier: str
    ) -> ReserveResult:
        """Atomically reserve credits within balance and the tier's daily cap."""
        granted = self.redis.eval(
            RESERVE_LUA,
            3,
            self._reserved_key(user_id),
            self._run_key(run_id),
            self._daily_key(user_id),
            str(amount),
            str(balance),
            str(RESERVATION_TTL_SECONDS),
            str(self.daily_cap(tier)),
            str(DAILY_COUNTER_TTL_SECONDS),
        )
        if granted == 1:
            return "ok"
        return "daily_cap_exceeded" if granted == -1 else "insufficient_balance"

    def settle(self, run_id: str, user: User, actual_cost: int | None = None) -> int:
        """Deduct the run's cost from the user's balance and free the hold."""
        reserved = self._get_int(self._run_key(run_id))
        cost = reserved if actual_cost is None else actual_cost
        user.credits_balance = max(0, user.credits_balance - cost)
        if cost < reserved:  # cheaper than reserved: refund the daily counter
            self._refund_daily(str(user.id), reserved - cost)
        self._release(str(user.id), run_id, reserved)
        return cost

    def release(self, user_id: str, run_id: str) -> None:
        """Free a reservation without charging (failed/cancelled runs)."""
        reserved = self._get_int(self._run_key(run_id))
        self._refund_daily(user_id, reserved)
        self._release(user_id, run_id, reserved)

    def _refund_daily(self, user_id: str, amount: int) -> None:
        if amount:
            self.redis.eval(DECR_FLOOR_LUA, 1, self._daily_key(user_id), str(amount))

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
