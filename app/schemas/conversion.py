import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

VALID_THEMES = {
    # Professional
    "clean_slate", "navy_gold", "dark_tech",
    "charcoal_amber", "steel_blue", "forest_pro",
    "midnight_black", "burgundy_suit", "prussian_blue",
    # Creative
    "vivid_purple", "sunset_orange", "ocean_teal",
    "neon_blue", "ruby_red", "cosmic_indigo",
    "rose_bloom", "electric_lime", "aurora",
    # Minimal
    "pure_white", "warm_ivory", "soft_grey",
    "light_pearl", "sage_mist", "warm_slate",
    "blush_rose", "arctic_sky", "mint_fresh",
}

VALID_STYLES = {"professional", "creative", "minimal", "bold", "executive", "technical", "narrative", "concise", "academic"}
VALID_AUDIENCES = {"c-suite", "technical", "general", "investors", "sales", "executive"}
VALID_FLAGS = {"minimal", "roadmap", "data_focus"}


class QAItem(BaseModel):
    question: str
    answer: str


class ConversionCreate(BaseModel):
    upload_id: uuid.UUID | None = None
    prompt_text: str | None = None
    theme: str = "clean_slate"
    style: str = "professional"
    audience_level: str = "general"
    slide_count: int = 10
    speaker_notes: bool = True
    questionnaire_answers: list[QAItem] = []
    presentation_flags: list[str] = []

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        if v not in VALID_THEMES:
            raise ValueError(f"Invalid theme: {v}. Valid: {', '.join(sorted(VALID_THEMES))}")
        return v

    @field_validator("slide_count")
    @classmethod
    def validate_slide_count(cls, v: int) -> int:
        if v <= 3:
            raise ValueError("slide_count must be greater than 3")
        if v > 50:
            raise ValueError("slide_count must not exceed 50")
        return v

    @field_validator("prompt_text")
    @classmethod
    def validate_prompt_text(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if len(v) < 20:
                raise ValueError("Prompt must be at least 20 characters")
            if len(v) > 3000:
                raise ValueError("Prompt must not exceed 3000 characters")
        return v

    @field_validator("presentation_flags")
    @classmethod
    def validate_flags(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_FLAGS
        if invalid:
            raise ValueError(f"Invalid flags: {', '.join(sorted(invalid))}. Valid: {', '.join(sorted(VALID_FLAGS))}")
        return list(set(v))  # deduplicate

    def model_post_init(self, __context: object) -> None:
        if not self.upload_id and not self.prompt_text:
            raise ValueError("Either upload_id or prompt_text is required")


class SlideOut(BaseModel):
    id: uuid.UUID
    position: int
    layout: str
    title: str | None
    bullets: list[str]
    text_styles: dict = {}
    speaker_notes: str | None
    is_deleted: bool
    color_scheme: str = "default"
    shape_style: str = "square"
    background_image_url: str | None = None
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
    name: str | None = None
    tokens_used: int
    source_pptx_key: str | None = None
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
