import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser, get_current_user
from auth.security import (
    JWTError,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from db import get_db, settings
from models.user import User
from schemas.auth import LoginRequest, TokenResponse, UserRead

router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        # No `domain` set — the cookie defaults to the request's own host, which
        # works unchanged for both localhost and the split capacity/api-capacity
        # subdomains in production.
        # "lax" is safe here even across the frontend/API subdomains in prod:
        # SameSite is evaluated per registrable domain ("adamrmunday.com"), not
        # per subdomain, so this is a same-site request in both environments —
        # it just isn't a cross-site one that Lax would need to block.
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/auth",
    )


async def _get_user_by_email(email: str, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await _get_user_by_email(payload.email, db)
    if user is None or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive")

    access_token = create_access_token(user_id=user.id, email=user.email, role=user.role, physician_id=user.physician_id)
    refresh_token = create_refresh_token(user_id=user.id)
    _set_refresh_cookie(response, refresh_token)

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return TokenResponse(access_token=access_token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    if refresh_token is None:
        raise unauthorized

    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise unauthorized

    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise unauthorized

    result = await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise unauthorized

    access_token = create_access_token(user_id=user.id, email=user.email, role=user.role, physician_id=user.physician_id)
    return TokenResponse(access_token=access_token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/api/auth")


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
