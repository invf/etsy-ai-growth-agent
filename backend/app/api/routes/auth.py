from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.models.session import UserSession
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_out(user: User) -> UserOut:
    # TODO: store_count once the stores table exists (Week 2)
    return UserOut(
        id=str(user.id),
        email=user.email,
        name=user.name,
        subscription_tier=user.subscription_tier,
        subscription_status=user.subscription_status,
        credits_balance=user.credits_balance,
        credits_available=user.credits_balance - user.credits_reserved,
        trial_ends_at=user.trial_ends_at.isoformat() if user.trial_ends_at else None,
        onboarding_completed=user.onboarding_completed,
        store_count=0,
    )


def _create_session(db: Session, user: User, refresh_token: str) -> None:
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(session)


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=dict)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = (
        db.query(User)
        .filter(User.email == body.email.lower(), User.deleted_at.is_(None))
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={"code": "EMAIL_ALREADY_EXISTS", "message": "Email already registered"},
        )

    user = User(
        email=body.email.lower(),
        name=body.name.strip(),
        password_hash=hash_password(body.password),
        timezone=body.timezone,
        subscription_status="trial",
        subscription_tier="trial",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
        credits_balance=30,
    )
    db.add(user)
    db.flush()  # get user.id without committing

    access_token, _ = create_access_token(str(user.id))
    refresh_token, _ = create_refresh_token(str(user.id))
    _create_session(db, user, refresh_token)

    return {
        "data": AuthResponse(
            user=_user_to_out(user),
            access_token=access_token,
            refresh_token=refresh_token,
        ).model_dump()
    }


@router.post("/login", response_model=dict)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .filter(User.email == body.email.lower(), User.deleted_at.is_(None))
        .first()
    )

    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"},
        )

    user.last_login_at = datetime.now(timezone.utc)

    access_token, _ = create_access_token(str(user.id))
    refresh_token, _ = create_refresh_token(str(user.id))
    _create_session(db, user, refresh_token)

    return {
        "data": AuthResponse(
            user=_user_to_out(user),
            access_token=access_token,
            refresh_token=refresh_token,
        ).model_dump()
    }


@router.post("/refresh", response_model=dict)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=401,
            detail={"code": "TOKEN_INVALID", "message": "Invalid refresh token"},
        )

    token_hash = hash_token(body.refresh_token)
    session_row = (
        db.query(UserSession)
        .filter(UserSession.token_hash == token_hash, UserSession.is_revoked.is_(False))
        .first()
    )

    if not session_row or session_row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=401,
            detail={"code": "TOKEN_EXPIRED", "message": "Refresh token expired"},
        )

    new_access, _ = create_access_token(payload["sub"])
    return {"data": {"access_token": new_access, "expires_in": 86400}}


@router.post("/logout", response_model=dict)
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Revoke all non-expired sessions for this user
    # (in production: revoke only the current token by passing it in the request)
    db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_revoked.is_(False),
    ).update({"is_revoked": True})
    return {"data": {"success": True}}


@router.get("/me", response_model=dict)
def me(current_user: User = Depends(get_current_user)):
    return {"data": _user_to_out(current_user).model_dump()}
