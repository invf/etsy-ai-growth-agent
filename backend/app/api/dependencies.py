from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models.user import User
from app.db.session import get_db

bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_INVALID", "message": "Invalid or expired token"},
        )

    user = (
        db.query(User)
        .filter(User.id == payload["sub"], User.deleted_at.is_(None))
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_INVALID", "message": "User not found"},
        )

    return user


def require_tier(required: str):
    TIER_RANK = {"trial": 0, "starter": 1, "growth": 2, "pro": 3, "agency": 4}

    def check(current_user: User = Depends(get_current_user)) -> User:
        user_rank = TIER_RANK.get(current_user.subscription_tier, 0)
        required_rank = TIER_RANK.get(required, 0)
        if user_rank < required_rank:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "UPGRADE_REQUIRED",
                    "message": f"This feature requires {required} plan or higher.",
                    "details": {
                        "required_tier": required,
                        "current_tier": current_user.subscription_tier,
                        "upgrade_url": "/billing/upgrade",
                    },
                },
            )
        return current_user

    return check
