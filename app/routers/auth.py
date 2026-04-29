import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.dependencies.db import get_db
from app.models.user import User
from app.models.user import User as RefreshTokenModel  # same file re-import clarity
from app.schemas.auth import RegisterRequest, RegisterResponse, TokenResponse, UserOut, ChangePasswordRequest
from app.services.audit import log_event
from app.dependencies.auth import get_current_user
from app.core.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

# We store refresh tokens in DB (refresh_tokens table) — import model lazily
from app.models import user  # noqa: ensure models registered


async def _create_refresh_token(db: AsyncSession, user_id: uuid.UUID) -> str:


    # Import inline to avoid circular
    from sqlalchemy.orm import Session
    import importlib

    # Lazy import of refresh token model
    from sqlalchemy import Column, String, Boolean, TIMESTAMP
    from sqlalchemy.dialects.postgresql import UUID as PUUID
    from app.core.database import Base

    # Use raw token in cookie, store hash
    raw = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # Insert into refresh_tokens
    await db.execute(
        __import__("sqlalchemy").text(
            "INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at) "
            "VALUES (:id, :user_id, :hash, :exp)"
        ),
        {"id": str(uuid.uuid4()), "user_id": str(user_id), "hash": token_hash, "exp": expires},
    )
    return raw


async def _verify_refresh_token(db: AsyncSession, raw: str) -> User | None:
    import sqlalchemy as sa
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    result = await db.execute(
        sa.text(
            "SELECT rt.user_id FROM refresh_tokens rt "
            "WHERE rt.token_hash = :hash AND rt.revoked = false AND rt.expires_at > :now"
        ),
        {"hash": token_hash, "now": now},
    )
    row = result.fetchone()
    if not row:
        return None
    user = await db.get(User, uuid.UUID(str(row[0])))
    if not user or not user.is_active:
        return None
    return user


async def _revoke_refresh_token(db: AsyncSession, raw: str) -> None:
    import sqlalchemy as sa
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    await db.execute(
        sa.text("UPDATE refresh_tokens SET revoked = true WHERE token_hash = :hash"),
        {"hash": token_hash},
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    secure = settings.ENVIRONMENT != "development"
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )


@router.post("/register", status_code=201, response_model=RegisterResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail={"code": "EMAIL_EXISTS", "message": "Email already registered"})

    user = User(
        id=uuid.uuid4(),
        email=body.email,
        password_hash=hash_password(body.password),
        name=body.name,
        role="user",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await log_event(db, "user.register", actor_id=user.id, target_type="user", target_id=user.id, metadata={"email": body.email})
    await db.commit()
    await db.refresh(user)
    return RegisterResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"code": "BAD_CREDENTIALS", "message": "Invalid email or password"})
    if not user.is_active:
        raise HTTPException(status_code=403, detail={"code": "SUSPENDED", "message": "Account suspended"})

    access_token = create_access_token({"user_id": str(user.id), "role": user.role, "email": user.email})
    refresh_raw = await _create_refresh_token(db, user.id)
    _set_refresh_cookie(response, refresh_raw)

    import sqlalchemy as sa
    await db.execute(
        sa.text("UPDATE users SET last_login = NOW() WHERE id = :id"),
        {"id": str(user.id)},
    )
    await log_event(db, "user.login", actor_id=user.id, target_type="user", target_id=user.id, metadata={"email": user.email})
    await db.commit()

    return TokenResponse(access_token=access_token, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail={"code": "NO_REFRESH_TOKEN", "message": "Refresh token missing"})

    user = await _verify_refresh_token(db, refresh_token)
    if not user:
        raise HTTPException(status_code=401, detail={"code": "INVALID_REFRESH_TOKEN", "message": "Invalid or expired refresh token"})

    # Rotate: revoke old, issue new
    await _revoke_refresh_token(db, refresh_token)
    new_raw = await _create_refresh_token(db, user.id)
    _set_refresh_cookie(response, new_raw)

    access_token = create_access_token({"user_id": str(user.id), "role": user.role, "email": user.email})
    return TokenResponse(access_token=access_token, user=UserOut.model_validate(user))


@router.patch("/password", status_code=200)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import sqlalchemy as sa
    # Fetch fresh row to avoid stale identity-map cache
    result = await db.execute(
        sa.text("SELECT password_hash FROM users WHERE id = :id"),
        {"id": str(current_user.id)},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found"})

    if not verify_password(body.current_password, row.password_hash):
        raise HTTPException(
            status_code=400,
            detail={"code": "WRONG_PASSWORD", "message": "Current password is incorrect"},
        )
    await db.execute(
        sa.text("UPDATE users SET password_hash = :hash WHERE id = :id"),
        {"hash": hash_password(body.new_password), "id": str(current_user.id)},
    )
    await log_event(db, "user.password_change", actor_id=current_user.id, target_type="user", target_id=current_user.id)
    await db.commit()
    return {"message": "Password updated successfully"}


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token:
        await _revoke_refresh_token(db, refresh_token)
        await log_event(db, "user.logout")
        await db.commit()
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    return {"message": "Logged out"}
