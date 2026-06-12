"""Self-service account endpoints. Every route acts ONLY on the authenticated
user resolved from the JWT - a user id is never accepted from the client."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.auth import hash_password, verify_password
from app.db import get_db
from app.models import Bracket, Message, User
from app.schemas import AccountDeleteRequest, UserProfileResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def _profile(user: User) -> UserProfileResponse:
    return UserProfileResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        country=user.country_region,
        timezone=user.timezone,
        daily_digest_opt_in=bool(user.daily_digest_opt_in),
        created_at=user.created_at,
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_me(user: User = Depends(get_current_user)):
    return _profile(user)


@router.patch("/me", response_model=UserProfileResponse)
async def update_me(
    data: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Uniqueness checks (only when the value actually changes), excluding self.
    if data.email is not None and data.email != user.email:
        clash = (
            await db.execute(select(User.id).where(User.email == data.email, User.id != user.id))
        ).first()
        if clash:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")
        user.email = data.email

    if data.username is not None and data.username != user.username:
        clash = (
            await db.execute(
                select(User.id).where(User.username == data.username, User.id != user.id)
            )
        ).first()
        if clash:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username already taken")
        user.username = data.username

    if data.country is not None:
        user.country_region = data.country
    if data.timezone is not None:
        user.timezone = data.timezone
    if data.daily_digest_opt_in is not None:
        user.daily_digest_opt_in = data.daily_digest_opt_in
    if data.password is not None:
        # Changing the password requires confirming the current one.
        if not data.current_password or not verify_password(
            data.current_password, user.hashed_password
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Current password is incorrect")
        user.hashed_password = hash_password(data.password)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email or username already taken")
    await db.refresh(user)
    return _profile(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    data: AccountDeleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Password is incorrect")

    # Cascade-delete dependent rows the user owns. followed_team_ids /
    # favorite_team_id live on the user row itself, so they go with it.
    await db.execute(delete(Bracket).where(Bracket.user_id == user.id))
    await db.execute(delete(Message).where(Message.user_id == user.id))
    await db.delete(user)
    await db.flush()
    return None
