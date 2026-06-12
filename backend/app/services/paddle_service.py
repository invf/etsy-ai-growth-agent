"""Paddle webhook processing: signature verification + event handlers.

Paddle is the merchant of record; these handlers keep users'
subscription state and credit balances in sync with billing events.
"""

import hashlib
import hmac
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.billing import CreditTransaction, SubscriptionPlan
from app.db.models.user import User

HANDLED_EVENTS = {
    "subscription.created",
    "subscription.updated",
    "subscription.cancelled",
    "subscription.paused",
    "subscription.resumed",
    "transaction.completed",  # subscription payments and one-time top-ups
    "transaction.payment_failed",
}


def verify_paddle_signature(
    body: bytes, signature_header: str | None, secret: str
) -> bool:
    """Paddle-Signature header: 'ts=<unix>;h1=<hmac-sha256(ts:body)>'."""
    if not signature_header or not secret:
        return False
    try:
        parts = dict(kv.split("=", 1) for kv in signature_header.split(";"))
    except ValueError:
        return False
    ts = parts.get("ts", "")
    received = parts.get("h1", "")
    signed_payload = f"{ts}:{body.decode()}"
    expected = hmac.new(
        secret.encode(), signed_payload.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class PaddleWebhookService:
    def __init__(self, db: Session):
        self.db = db

    def handle(self, event_type: str, data: dict) -> uuid.UUID | None:
        """Process one event; returns the affected user id when resolvable."""
        handler = {
            "subscription.created": self._on_subscription_created,
            "subscription.updated": self._on_subscription_updated,
            "subscription.cancelled": self._on_subscription_cancelled,
            "subscription.paused": self._on_subscription_paused,
            "subscription.resumed": self._on_subscription_resumed,
            "transaction.completed": self._on_transaction_completed,
            "transaction.payment_failed": self._on_payment_failed,
        }[event_type]
        user = handler(data)
        return user.id if user else None

    # --- lookups -------------------------------------------------------

    def _user_by_custom_data(self, data: dict) -> User | None:
        user_id = (data.get("custom_data") or {}).get("user_id")
        if not user_id:
            return None
        return self.db.query(User).filter_by(id=user_id).first()

    def _user_by_subscription(self, subscription_id: str | None) -> User | None:
        if not subscription_id:
            return None
        return (
            self.db.query(User)
            .filter_by(paddle_subscription_id=subscription_id)
            .first()
        )

    def _resolve_user(self, data: dict) -> User | None:
        return self._user_by_custom_data(data) or self._user_by_subscription(
            data.get("subscription_id") or data.get("id")
        )

    def _plan_for_price(self, price_id: str | None) -> SubscriptionPlan | None:
        """Price IDs live on subscription_plans (set via admin, not env)."""
        if not price_id:
            return None
        for plan in self.db.query(SubscriptionPlan).filter_by(is_active=True).all():
            if price_id in (plan.paddle_price_id_monthly, plan.paddle_price_id_annual):
                return plan
        return None

    def _plan_by_name(self, name: str) -> SubscriptionPlan | None:
        return self.db.query(SubscriptionPlan).filter_by(name=name).first()

    @staticmethod
    def _price_id(data: dict) -> str | None:
        items = data.get("items") or []
        if not items:
            return None
        return ((items[0].get("price") or {}).get("id")) or None

    # --- credit ledger ---------------------------------------------------

    def _grant_credits(
        self,
        user: User,
        amount: int,
        transaction_type: str,
        paddle_transaction_id: str | None = None,
        notes: str | None = None,
    ) -> None:
        if amount <= 0:
            return
        user.credits_balance += amount
        self.db.add(
            CreditTransaction(
                user_id=user.id,
                amount=amount,
                balance_after=user.credits_balance,
                transaction_type=transaction_type,
                paddle_transaction_id=paddle_transaction_id,
                notes=notes,
            )
        )

    # --- handlers --------------------------------------------------------

    def _on_subscription_created(self, data: dict) -> User | None:
        user = self._user_by_custom_data(data)
        if not user:
            return None
        plan = self._plan_for_price(self._price_id(data))

        user.subscription_status = "active"
        user.paddle_subscription_id = data.get("id")
        user.paddle_customer_id = data.get("customer_id")
        user.trial_ends_at = None
        user.subscription_started_at = datetime.now(timezone.utc)
        user.subscription_current_period_end = _parse_dt(data.get("next_billed_at"))
        billing_period = (data.get("custom_data") or {}).get("billing_period")
        if billing_period in ("monthly", "annual"):
            user.billing_interval = billing_period
        if plan:
            user.subscription_tier = plan.name
            self._grant_credits(
                user,
                plan.credits_monthly,
                "subscription_renewal",
                notes=f"First {plan.name} allocation",
            )
        return user

    def _on_subscription_updated(self, data: dict) -> User | None:
        user = self._resolve_user(data)
        if not user:
            return None
        user.subscription_current_period_end = _parse_dt(data.get("next_billed_at"))

        new_plan = self._plan_for_price(self._price_id(data))
        if not new_plan or new_plan.name == user.subscription_tier:
            return user

        old_plan = self._plan_by_name(user.subscription_tier)
        user.subscription_tier = new_plan.name
        # Upgrade: immediately top up the difference in monthly credits
        diff = new_plan.credits_monthly - (old_plan.credits_monthly if old_plan else 0)
        self._grant_credits(
            user,
            diff,
            "subscription_renewal",
            notes=f"Upgrade adjustment to {new_plan.name}",
        )
        return user

    def _on_subscription_cancelled(self, data: dict) -> User | None:
        user = self._resolve_user(data)
        if not user:
            return None
        # Takes effect at period end: 'cancelling' now, 'cancelled' later
        user.subscription_status = "cancelling"
        user.subscription_cancelled_at = datetime.now(timezone.utc)
        return user

    def _on_subscription_paused(self, data: dict) -> User | None:
        user = self._resolve_user(data)
        if user:
            user.subscription_status = "paused"
        return user

    def _on_subscription_resumed(self, data: dict) -> User | None:
        user = self._resolve_user(data)
        if user:
            user.subscription_status = "active"
        return user

    def _on_transaction_completed(self, data: dict) -> User | None:
        custom = data.get("custom_data") or {}

        if custom.get("transaction_type") == "credit_topup":
            user = self._user_by_custom_data(data)
            credits = int(custom.get("credits") or 0)
            if user and credits > 0:
                self._grant_credits(
                    user,
                    credits,
                    "topup_purchase",
                    paddle_transaction_id=data.get("id"),
                    notes="Credit top-up",
                )
            return user

        # Renewal payments only — the first payment's credits are granted
        # by subscription.created, so don't double-allocate here
        if data.get("origin") != "subscription_recurring":
            return None
        user = self._user_by_subscription(data.get("subscription_id"))
        if not user:
            return None
        plan = self._plan_by_name(user.subscription_tier)
        if plan:
            self._grant_credits(
                user,
                plan.credits_monthly,
                "subscription_renewal",
                paddle_transaction_id=data.get("id"),
                notes=f"Monthly {plan.name} allocation",
            )
        user.subscription_status = "active"
        return user

    def _on_payment_failed(self, data: dict) -> User | None:
        user = self._user_by_subscription(data.get("subscription_id"))
        if user:
            user.subscription_status = "past_due"
        return user
