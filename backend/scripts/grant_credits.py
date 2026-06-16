"""Set a user's credit balance (admin / testing helper).

Usage (run from the backend dir, e.g. the Render shell, where DATABASE_URL_SYNC
and app deps are available):

    python -m scripts.grant_credits <email-or-user-id> <amount>

Examples:
    python -m scripts.grant_credits korvik16@gmail.com 1000
    python -m scripts.grant_credits 6bc956e9-f372-44fa-b66c-146bba77a390 1000

This sets `users.credits_balance` to <amount> (the total balance, separate from
the per-day cap in Redis). It does not touch Redis reservations.
"""

import sys

from app.db.models.user import User
from app.db.session import get_db_session


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python -m scripts.grant_credits <email-or-user-id> <amount>")
        return 1

    ident, raw_amount = sys.argv[1], sys.argv[2]
    try:
        amount = int(raw_amount)
    except ValueError:
        print(f"amount must be an integer, got: {raw_amount!r}")
        return 1
    if amount < 0:
        print("amount must be >= 0")
        return 1

    with get_db_session() as db:
        query = db.query(User)
        user = (
            query.filter(User.email == ident).first()
            if "@" in ident
            else query.filter(User.id == ident).first()
        )
        if user is None:
            print(f"user not found: {ident}")
            return 1
        old = user.credits_balance
        user.credits_balance = amount
        print(f"{user.email}: credits_balance {old} -> {amount}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
