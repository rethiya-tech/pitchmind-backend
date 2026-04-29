import uuid
from datetime import datetime

from pydantic import BaseModel


class SlidePatch(BaseModel):
    title: str | None = None
    bullets: list[str] | None = None
    speaker_notes: str | None = None
    layout: str | None = None


class SlideInsert(BaseModel):
    position: int = 0
    title: str = ""
    bullets: list[str] = []
    speaker_notes: str = ""
    layout: str = "bullets"


class SlideReorder(BaseModel):
    slide_ids: list[uuid.UUID]


class SlideOut(BaseModel):
    id: uuid.UUID
    conversion_id: uuid.UUID
    position: int
    layout: str
    title: str | None
    bullets: list[str]
    speaker_notes: str | None
    is_deleted: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
