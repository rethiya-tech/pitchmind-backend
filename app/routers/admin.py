import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.db import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.admin import (
    AdminConversionListResponse,
    AdminConversionOut,
    AdminMetrics,
    AdminUserCreate,
    AdminUserListResponse,
    AdminUserOut,
    AdminUserPatch,
    AuditLogEntry,
    AuditLogListResponse,
)
from app.core.security import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics", response_model=AdminMetrics)
async def get_metrics(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    total_result = await db.execute(sa.text("SELECT COUNT(*) FROM users"))
    total_users = total_result.scalar() or 0

    total_conv_result = await db.execute(sa.text("SELECT COUNT(*) FROM conversions"))
    total_conversions = total_conv_result.scalar() or 0

    conv_today = await db.execute(
        sa.text(
            "SELECT COUNT(*) FROM conversions "
            "WHERE created_at >= NOW() - INTERVAL '1 day'"
        )
    )
    conversions_today = conv_today.scalar() or 0

    failed_today = await db.execute(
        sa.text(
            "SELECT COUNT(*) FROM conversions "
            "WHERE status = 'failed' AND created_at >= NOW() - INTERVAL '1 day'"
        )
    )
    failed = failed_today.scalar() or 0

    cost_result = await db.execute(
        sa.text(
            "SELECT COALESCE(SUM(tokens_used), 0) FROM conversions "
            "WHERE created_at >= NOW() - INTERVAL '1 day'"
        )
    )
    tokens_today = cost_result.scalar() or 0

    total_tokens_result = await db.execute(
        sa.text("SELECT COALESCE(SUM(tokens_used), 0) FROM conversions")
    )
    total_tokens = total_tokens_result.scalar() or 0

    done_result = await db.execute(
        sa.text("SELECT COUNT(*) FROM conversions WHERE status = 'done'")
    )
    done_conversions = done_result.scalar() or 0

    slides_result = await db.execute(
        sa.text("SELECT COALESCE(SUM(slide_count), 0) FROM conversions WHERE status = 'done'")
    )
    total_slides = slides_result.scalar() or 0

    active_today_result = await db.execute(
        sa.text("SELECT COUNT(*) FROM users WHERE last_login >= NOW() - INTERVAL '1 day'")
    )
    active_users_today = active_today_result.scalar() or 0

    success_rate = round((done_conversions / total_conversions * 100), 1) if total_conversions > 0 else 0.0

    return AdminMetrics(
        total_users=total_users,
        active_users_today=active_users_today,
        total_conversions=total_conversions,
        done_conversions=done_conversions,
        conversions_today=conversions_today,
        failed_today=failed,
        total_slides=total_slides,
        success_rate=success_rate,
        ai_cost_today_usd=float(tokens_today) * 0.000003,
        ai_cost_total_usd=float(total_tokens) * 0.000003,
        total_tokens=total_tokens,
    )


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    offset = (page - 1) * page_size

    if search:
        where = "WHERE email ILIKE :search OR name ILIKE :search"
        params: dict = {"search": f"%{search}%"}
    else:
        where = ""
        params = {}

    total_result = await db.execute(
        sa.text(f"SELECT COUNT(*) FROM users {where}"),
        params,
    )
    total = total_result.scalar() or 0

    rows = await db.execute(
        sa.text(
            f"SELECT u.*, "
            f"(SELECT COUNT(*) FROM conversions c WHERE c.user_id = u.id) AS conversion_count "
            f"FROM users u {where} "
            f"ORDER BY u.created_at DESC "
            f"LIMIT :limit OFFSET :offset"
        ),
        {**params, "limit": page_size, "offset": offset},
    )

    items = []
    for row in rows.mappings():
        items.append(AdminUserOut(
            id=row["id"],
            email=row["email"],
            name=row.get("name"),
            role=row["role"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            conversion_count=row["conversion_count"],
        ))

    return AdminUserListResponse(items=items, total=total, page=page)


@router.get("/users/{user_id}", response_model=AdminUserOut)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found"})
    row = await db.execute(
        sa.text(
            "SELECT u.*, "
            "(SELECT COUNT(*) FROM conversions c WHERE c.user_id = u.id) AS conversion_count "
            "FROM users u WHERE u.id = :id"
        ),
        {"id": str(uid)},
    )
    result = row.mappings().fetchone()
    if not result:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found"})

    return AdminUserOut(
        id=result["id"],
        email=result["email"],
        name=result.get("name"),
        role=result["role"],
        is_active=result["is_active"],
        created_at=result["created_at"],
        conversion_count=result["conversion_count"],
    )


@router.post("/users", status_code=201, response_model=AdminUserOut)
async def create_user(
    body: AdminUserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = await db.execute(sa.text("SELECT id FROM users WHERE email = :email"), {"email": body.email})
    if existing.fetchone():
        raise HTTPException(status_code=409, detail={"code": "EMAIL_EXISTS", "message": "Email already registered"})

    if body.role not in ("user", "admin"):
        raise HTTPException(status_code=422, detail={"code": "INVALID_ROLE", "message": "Role must be user or admin"})

    new_id = str(uuid.uuid4())
    await db.execute(
        sa.text(
            "INSERT INTO users (id, email, password_hash, name, role, is_active, created_at) "
            "VALUES (:id, :email, :password_hash, :name, :role, true, NOW())"
        ),
        {
            "id": new_id,
            "email": body.email,
            "password_hash": hash_password(body.password),
            "name": body.name,
            "role": body.role,
        },
    )
    await db.flush()

    return AdminUserOut(
        id=uuid.UUID(new_id),
        email=body.email,
        name=body.name,
        role=body.role,
        is_active=True,
        created_at=__import__("datetime").datetime.utcnow(),
        conversion_count=0,
    )


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def patch_user(
    user_id: str,
    body: AdminUserPatch,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found"})
    # Prevent self-suspension
    if uid == admin.id and body.is_active is False:
        raise HTTPException(status_code=409, detail={"code": "SELF_SUSPEND", "message": "Cannot suspend yourself"})

    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found"})

    if body.email is not None:
        existing = await db.execute(
            sa.text("SELECT id FROM users WHERE email = :email AND id != :id"),
            {"email": body.email, "id": str(uid)},
        )
        if existing.fetchone():
            raise HTTPException(status_code=409, detail={"code": "EMAIL_EXISTS", "message": "Email already in use"})

    updates: dict = {}
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    if body.role is not None:
        updates["role"] = body.role
    if body.name is not None:
        updates["name"] = body.name
    if body.email is not None:
        updates["email"] = body.email
    if body.password is not None:
        updates["password_hash"] = hash_password(body.password)

    if updates:
        set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
        params = {**updates, "id": str(uid)}
        await db.execute(
            sa.text(f"UPDATE users SET {set_clauses} WHERE id = :id"),
            params,
        )
        await db.flush()
        await db.refresh(user)

    # Get conversion count
    count_result = await db.execute(
        sa.text("SELECT COUNT(*) FROM conversions WHERE user_id = :uid"),
        {"uid": str(uid)},
    )
    conv_count = count_result.scalar() or 0

    return AdminUserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        conversion_count=conv_count,
    )


@router.get("/conversions", response_model=AdminConversionListResponse)
async def list_all_conversions(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    offset = (page - 1) * page_size

    total_result = await db.execute(sa.text("SELECT COUNT(*) FROM conversions"))
    total = total_result.scalar() or 0

    rows = await db.execute(
        sa.text(
            "SELECT c.id, c.user_id, c.original_filename, c.status, c.theme, "
            "c.slide_count, c.tokens_used, c.created_at, "
            "u.email AS user_email, u.name AS user_name "
            "FROM conversions c "
            "LEFT JOIN users u ON c.user_id = u.id "
            "ORDER BY c.created_at DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        {"limit": page_size, "offset": offset},
    )

    items = []
    for row in rows.mappings():
        items.append(AdminConversionOut(
            id=row["id"],
            user_id=row["user_id"],
            user_email=row.get("user_email"),
            user_name=row.get("user_name"),
            original_filename=row.get("original_filename"),
            status=row["status"],
            theme=row.get("theme"),
            slide_count=row.get("slide_count"),
            tokens_used=row.get("tokens_used"),
            created_at=row["created_at"],
        ))

    return AdminConversionListResponse(items=items, total=total, page=page)


@router.get("/audit-log", response_model=AuditLogListResponse)
async def get_audit_log(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    offset = (page - 1) * page_size

    total_result = await db.execute(sa.text("SELECT COUNT(*) FROM audit_log"))
    total = total_result.scalar() or 0

    rows = await db.execute(
        sa.text(
            "SELECT al.*, u.email AS actor_email "
            "FROM audit_log al "
            "LEFT JOIN users u ON al.actor_id = u.id "
            "ORDER BY al.created_at DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        {"limit": page_size, "offset": offset},
    )

    items = []
    for row in rows.mappings():
        items.append(AuditLogEntry(
            id=row["id"],
            actor_email=row.get("actor_email"),
            action=row["action"],
            target_type=row.get("target_type"),
            target_id=row.get("target_id"),
            metadata=row.get("metadata") or {},
            created_at=row["created_at"],
        ))

    return AuditLogListResponse(items=items, total=total, page=page)
