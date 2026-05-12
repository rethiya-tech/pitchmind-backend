import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request
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
import logging

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/conversions", tags=["export"])

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


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

    # Fetch the original upload if this conversion came from a file
    upload = None
    if conv.upload_id:
        upload = await db.get(Upload, conv.upload_id)

    return cid, conv, slides, upload


def _build_pptx_bytes(conv: Any, slides: list, upload: Any = None) -> bytes:
    """Build PPTX bytes, preserving original design when possible.

    Priority:
      1. Template-based conversion (Use Template flow) — source_pptx_key
      2. Direct PPTX upload — original uploaded file
      3. Fallback to app theme builder
    """
    # 1. Template copy flow
    if conv.source_pptx_key:
        template_bytes = gcs.read_pptx_key_bytes(conv.source_pptx_key)
        if template_bytes:
            _log.info("Export %s: using original template PPTX", conv.id)
            return pptx_builder.build_pptx_from_template(slides, template_bytes)
        _log.warning("Export %s: template PPTX missing at %s, falling back", conv.id, conv.source_pptx_key)

    # 2. Direct PPTX upload — use theme builder so edited content is exported,
    #    not the original file (template-preserving path is only for explicit template copies)

    # 3. App theme builder
    theme_id = conv.theme or "clean_slate"
    try:
        theme = theme_svc.get_theme(theme_id)
    except KeyError:
        theme = theme_svc.get_theme("clean_slate")
    return pptx_builder.build_pptx(slides, theme)


@router.get("/{conversion_id}/download", include_in_schema=False)
async def download_pptx_local(
    conversion_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dev-only: build and stream PPTX directly without GCS."""
    cid, conv, slides, upload = await _load_slides_for_export(conversion_id, current_user, db)
    pptx_bytes = _build_pptx_bytes(conv, slides, upload)
    filename = (conv.original_filename or "presentation").rsplit(".", 1)[0] + ".pptx"
    return Response(
        content=pptx_bytes,
        media_type=PPTX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{conversion_id}/export", response_model=ExportResponse)
async def export_pptx(
    conversion_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = get_settings()
    cid, conv, slides, upload = await _load_slides_for_export(conversion_id, current_user, db)
    pptx_bytes = _build_pptx_bytes(conv, slides, upload)

    if not gcs.is_configured():
        base = (settings.BACKEND_URL or str(request.base_url)).rstrip("/")
        download_url = f"{base}/api/v1/conversions/{cid}/download"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        return ExportResponse(download_url=download_url, expires_at=expires_at)

    pptx_key = gcs.generate_pptx_key(str(cid))
    gcs.upload_bytes(
        bucket=settings.GCS_BUCKET,
        key=pptx_key,
        data=pptx_bytes,
        content_type=PPTX_MIME,
    )
    download_url = gcs.get_signed_download_url(
        bucket=settings.GCS_BUCKET,
        key=pptx_key,
        expiry_hours=1,
    )
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    return ExportResponse(download_url=download_url, expires_at=expires_at)
