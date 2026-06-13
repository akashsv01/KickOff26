import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.auth import (
    create_access_token,
    create_user,
    generate_reset_token,
    get_user_by_email,
    get_user_by_username,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.data.country_timezones import default_signup_timezone
from app.db import get_db
from app.models import User
from app.schemas import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.email_service import (
    PASSWORD_RESET_TTL_MINUTES,
    send_password_reset_email,
    send_welcome_email,
)
from app.services.user_teams import merge_followed_team_ids, validate_official_team_ids

router = APIRouter(prefix="/auth", tags=["auth"])

# Best-effort in-memory cooldown to curb forgot-password email bombing. Single
# instance only; for multi-instance deploys add a gateway/middleware rate limiter
# (e.g. slowapi) keyed by IP + email. Never changes the response (no enumeration).
_RESET_COOLDOWN_SECONDS = 60
_recent_reset_requests: dict[str, float] = {}


def _allow_reset_email(email: str) -> bool:
    now = time.monotonic()
    last = _recent_reset_requests.get(email)
    if last is not None and now - last < _RESET_COOLDOWN_SECONDS:
        return False
    _recent_reset_requests[email] = now
    return True


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@router.post("/register", response_model=TokenResponse)
async def register(
    data: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    existing = await get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    taken = await get_user_by_username(db, data.username)
    if taken:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")
    try:
        follow_ids = merge_followed_team_ids(data.favorite_team_id, data.followed_team_ids)
        await validate_official_team_ids(db, follow_ids)
        user = await create_user(
            db,
            data.email,
            data.username,
            data.password,
            favorite_team_id=data.favorite_team_id,
            country_region=data.country_region,
            preferred_language=data.preferred_language,
            # Country wins for known countries (India -> Asia/Kolkata); the
            # auto-detected browser zone is only a fallback for "Other"/unlisted.
            timezone=default_signup_timezone(data.country_region, data.timezone),
            daily_digest_opt_in=data.daily_digest_opt_in,
            followed_team_ids=follow_ids,
        )
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email or username already taken")
    token = create_access_token(user.id)
    # Non-blocking welcome email - runs after the user is committed (get_db commits
    # on a successful response) and never blocks or fails the signup.
    background_tasks.add_task(send_welcome_email, user.id)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Always returns the same response - never reveals whether an account exists.

    If the email matches a user, store a hashed, single-use, short-lived token and
    email the raw token as a reset link (non-blocking). A send failure or a missing
    account both yield the identical neutral response.
    """
    generic = {"detail": "If an account exists for that email, a reset link has been sent."}
    user = await get_user_by_email(db, data.email)
    if user and _allow_reset_email(data.email):
        raw_token, token_hash = generate_reset_token()
        user.password_reset_token_hash = token_hash
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=PASSWORD_RESET_TTL_MINUTES
        )
        background_tasks.add_task(send_password_reset_email, user.id, raw_token)
    return generic


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Validate a reset token (hashed lookup, non-expired), set the new password, single-use."""
    token_hash = hash_reset_token(data.token)
    user = (
        await db.execute(select(User).where(User.password_reset_token_hash == token_hash))
    ).scalar_one_or_none()
    expires = _as_utc(user.password_reset_expires_at) if user else None
    if user is None or expires is None or expires < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired. Please request a new one.",
        )
    # Set the new password and invalidate the token (single-use).
    user.hashed_password = hash_password(data.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    return {"detail": "Password updated. You can now sign in with your new password."}


@router.get("/me", response_model=UserResponse)
async def me(user=Depends(get_current_user)):
    return UserResponse.model_validate(user)
