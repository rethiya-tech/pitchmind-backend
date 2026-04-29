import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Integer, String, TIMESTAMP, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    gcs_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    parse_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending", default="pending",
    )
    parsed_doc: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    parsed_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "parse_status IN ('pending','done','failed')",
            name="uploads_parse_status_check",
        ),
    )
