from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.auth import create_access_token, create_user, get_user_by_email, get_user_by_username, verify_password
from app.data.country_timezones import default_signup_timezone
from app.db import get_db
from app.schemas import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.user_teams import merge_followed_team_ids, validate_official_team_ids

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
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
            followed_team_ids=follow_ids,
        )
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email or username already taken")
    token = create_access_token(user.id)
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


@router.get("/me", response_model=UserResponse)
async def me(user=Depends(get_current_user)):
    return UserResponse.model_validate(user)
