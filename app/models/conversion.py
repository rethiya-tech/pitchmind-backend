import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Integer, String, TIMESTAMP, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Conversion(Base):
    __tablename__ = "conversions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    upload_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending", default="pending",
    )
    style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    slide_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    theme: Mapped[str | None] = mapped_column(String(100), nullable=True)
    audience_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    speaker_notes: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", default=True,
    )
    tokens_used: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','generating','done','failed','cancelled')",
            name="conversions_status_check",
        ),
    )
