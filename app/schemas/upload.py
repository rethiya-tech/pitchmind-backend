import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/markdown",
}


class PresignRequest(BaseModel):
    filename: str
    content_type: str
    size_bytes: int = 0

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if v not in ALLOWED_MIME_TYPES:
            raise ValueError(f"Unsupported file type: {v}. Allowed: {', '.join(ALLOWED_MIME_TYPES)}")
        return v


class PresignResponse(BaseModel):
    upload_url: str
    gcs_key: str
    upload_id: uuid.UUID


class ConfirmResponse(BaseModel):
    upload_id: uuid.UUID
    parse_status: str

    model_config = {"from_attributes": True}


class UploadOut(BaseModel):
    id: uuid.UUID
    original_filename: str
    mime_type: str
    file_size_bytes: int
    parse_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadListResponse(BaseModel):
    items: list[UploadOut]
    total: int


class PreviewResponse(BaseModel):
    preview_text: str
    word_count: int
