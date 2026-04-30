import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Integer, String, TIMESTAMP, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Slide(Base):
    __tablename__ = "slides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    conversion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    layout: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="bullets", default="bullets",
    )
    color_scheme: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="default", default="default",
    )
    shape_style: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="square", default="square",
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bullets: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default="[]", default=list,
    )
    speaker_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False,
    )
