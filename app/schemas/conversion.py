import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

VALID_THEMES = {
    "clean_slate", "navy_gold", "dark_tech",
    "charcoal_amber", "steel_blue", "forest_pro",
}

VALID_STYLES = {"executive", "technical", "narrative", "concise", "academic"}
VALID_AUDIENCES = {"c-suite", "technical", "general", "investors", "sales"}


class ConversionCreate(BaseModel):
    upload_id: uuid.UUID
    theme: str = "clean_slate"
    style: str = "executive"
    audience_level: str = "general"
    slide_count: int = 10
    speaker_notes: bool = True

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        if v not in VALID_THEMES:
            raise ValueError(f"Invalid theme: {v}. Valid: {', '.join(sorted(VALID_THEMES))}")
        return v

    @field_validator("slide_count")
    @classmethod
    def validate_slide_count(cls, v: int) -> int:
        if not 3 <= v <= 30:
            raise ValueError("slide_count must be between 3 and 30")
        return v


class SlideOut(BaseModel):
    id: uuid.UUID
    position: int
    layout: str
    title: str | None
    bullets: list[str]
    speaker_notes: str | None
    is_deleted: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversionOut(BaseModel):
    id: uuid.UUID
    status: str
    style: str | None
    theme: str | None
    slide_count: int | None
    audience_level: str | None
    original_filename: str | None
    tokens_used: int
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ConversionDetail(ConversionOut):
    slides: list[SlideOut] = []


class ConversionListResponse(BaseModel):
    items: list[ConversionOut]
    total: int


class ConversionCreateResponse(BaseModel):
    id: uuid.UUID
    status: str
    estimated_slides: int
    estimated_seconds: int


class CancelResponse(BaseModel):
    message: str
    slides_completed: int
