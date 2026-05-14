import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.models.conversion import Conversion
from app.models.slide import Slide
from app.models.upload import Upload
from app.models.user import User
from app.services import gcs, pptx_builder, themes as theme_svc
from app.services import docx_builder, pdf_converter
import logging

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/conversions", tags=["export"])

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
PDF_MIME  = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

ExportFormat = Literal["pptx", "pdf", "docx"]


class ExportResponse(BaseModel):
    download_url: str
    expires_at: datetime


async def _load_slides_for_export(conversion_id: str, current_user: User, db: AsyncSession):
    try:
        cid = uuid.UUID(conversion_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Conversion not found"})

    conv = await db.get(Conversion, cid)
    if not conv or (conv.user_id != current_user.id and current_user.role != "admin"):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Conversion not found"})

    result = await db.execute(
        sa.select(Slide)
        .where(Slide.conversion_id == cid, Slide.is_deleted == False)
        .order_by(Slide.position)
    )
    slides = result.scalars().all()
    if not slides:
        raise HTTPException(status_code=422, detail={"code": "NO_SLIDES", "message": "No slides to export"})

    upload = None
    if conv.upload_id:
        upload = await db.get(Upload, conv.upload_id)

    return cid, conv, slides, upload


def _build_pptx_bytes(conv: Any, slides: list, upload: Any = None) -> bytes:
    """Build PPTX bytes, preserving original design when possible."""
    if conv.source_pptx_key:
        template_bytes = gcs.read_pptx_key_bytes(conv.source_pptx_key)
        if template_bytes:
            _log.info("Export %s: using original template PPTX", conv.id)
            return pptx_builder.build_pptx_from_template(slides, template_bytes)
        _log.warning("Export %s: template PPTX missing at %s, falling back", conv.id, conv.source_pptx_key)

    theme_id = conv.theme or "clean_slate"
    try:
        theme = theme_svc.get_theme(theme_id)
    except KeyError:
        theme = theme_svc.get_theme("clean_slate")
    return pptx_builder.build_pptx(slides, theme)


async def _build_export_bytes(fmt: ExportFormat, conv: Any, slides: list, upload: Any = None) -> tuple[bytes, str, str]:
    """Return (file_bytes, mime_type, file_extension)."""
    if fmt == "pdf":
        pptx_bytes = _build_pptx_bytes(conv, slides, upload)
        pdf_bytes = await pdf_converter.convert_pptx_to_pdf(pptx_bytes)
        return pdf_bytes, PDF_MIME, "pdf"
    if fmt == "docx":
        return docx_builder.build_docx(slides), DOCX_MIME, "docx"
    # default: pptx
    return _build_pptx_bytes(conv, slides, upload), PPTX_MIME, "pptx"


@router.get("/{conversion_id}/download", include_in_schema=False)
async def download_local(
    conversion_id: str,
    format: ExportFormat = Query(default="pptx"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dev-only: build and stream file directly without GCS."""
    cid, conv, slides, upload = await _load_slides_for_export(conversion_id, current_user, db)
    try:
        file_bytes, mime, ext = await _build_export_bytes(format, conv, slides, upload)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail={"code": "CONVERSION_ERROR", "message": str(e)})

    base_name = (conv.original_filename or conv.name or "presentation").rsplit(".", 1)[0]
    filename = f"{base_name}.{ext}"
    return Response(
        content=file_bytes,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{conversion_id}/export", response_model=ExportResponse)
async def export_file(
    conversion_id: str,
    request: Request,
    format: ExportFormat = Query(default="pptx"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = get_settings()
    cid, conv, slides, upload = await _load_slides_for_export(conversion_id, current_user, db)

    try:
        file_bytes, mime, ext = await _build_export_bytes(format, conv, slides, upload)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail={"code": "CONVERSION_ERROR", "message": str(e)})

    if not gcs.is_configured():
        base = (settings.BACKEND_URL or str(request.base_url)).rstrip("/")
        download_url = f"{base}/api/v1/conversions/{cid}/download?format={format}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        return ExportResponse(download_url=download_url, expires_at=expires_at)

    key = gcs.generate_pptx_key(str(cid)).replace(".pptx", f".{ext}")
    gcs.upload_bytes(
        bucket=settings.GCS_BUCKET,
        key=key,
        data=file_bytes,
        content_type=mime,
    )
    download_url = gcs.get_signed_download_url(
        bucket=settings.GCS_BUCKET,
        key=key,
        expiry_hours=1,
    )
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    return ExportResponse(download_url=download_url, expires_at=expires_at)
