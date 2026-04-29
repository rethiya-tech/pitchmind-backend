import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AdminMetrics(BaseModel):
    total_users: int
    active_users_today: int = 0
    total_conversions: int = 0
    done_conversions: int = 0
    conversions_today: int
    failed_today: int
    total_slides: int = 0
    success_rate: float = 0.0
    ai_cost_today_usd: float
    ai_cost_total_usd: float = 0.0
    total_tokens: int = 0


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    role: str
    is_active: bool
    created_at: datetime
    conversion_count: int = 0

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int


class AdminUserPatch(BaseModel):
    is_active: bool | None = None
    role: str | None = None


class AdminConversionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    user_email: str | None
    user_name: str | None
    original_filename: str | None
    status: str
    theme: str | None
    slide_count: int | None
    tokens_used: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminConversionListResponse(BaseModel):
    items: list[AdminConversionOut]
    total: int
    page: int


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    actor_email: str | None
    action: str
    target_type: str | None
    target_id: uuid.UUID | None
    metadata: Any
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int
    page: int
