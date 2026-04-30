import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TemplateSlide(BaseModel):
    position: int
    layout: str = "bullets"
    title: str = ""
    bullets: list[str] = []
    speaker_notes: str = ""


class TemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    thumbnail_url: str | None
    slide_count: int
    theme: str | None
    is_active: bool
    created_at: datetime
    parse_warning: str | None = None

    model_config = {"from_attributes": True}


class TemplateDetail(TemplateOut):
    slides_json: list[Any]


class TemplateListResponse(BaseModel):
    items: list[TemplateOut]
    total: int


class TemplateCopyResponse(BaseModel):
    conversion_id: uuid.UUID
    slide_count: int
