import uuid
from datetime import datetime, timedelta, timezone

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
from app.models.user import User
from app.services import gcs, pptx_builder, themes as theme_svc

router = APIRouter(prefix="/conversions", tags=["export"])


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

    theme_id = conv.theme or "executive_gold"
    try:
        theme = theme_svc.get_theme(theme_id)
    except KeyError:
        theme = theme_svc.get_theme("executive_gold")

    return cid, conv, slides, theme


@router.get("/{conversion_id}/download", include_in_schema=False)
async def download_pptx_local(
    conversion_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dev-only: build and stream PPTX directly without GCS."""
    cid, conv, slides, theme = await _load_slides_for_export(conversion_id, current_user, db)
    pptx_bytes = pptx_builder.build_pptx(slides, theme)
    filename = (conv.original_filename or "presentation").rsplit(".", 1)[0] + ".pptx"
    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
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
    cid, conv, slides, theme = await _load_slides_for_export(conversion_id, current_user, db)
    pptx_bytes = pptx_builder.build_pptx(slides, theme)

    if not gcs.is_configured():
        # Local dev: return direct download URL served by this backend
        base = str(request.base_url).rstrip("/")
        download_url = f"{base}/api/v1/conversions/{cid}/download"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        return ExportResponse(download_url=download_url, expires_at=expires_at)

    pptx_key = gcs.generate_pptx_key(str(cid))
    gcs.upload_bytes(
        bucket=settings.GCS_BUCKET,
        key=pptx_key,
        data=pptx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    download_url = gcs.get_signed_download_url(
        bucket=settings.GCS_BUCKET,
        key=pptx_key,
        expiry_hours=1,
    )
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    return ExportResponse(download_url=download_url, expires_at=expires_at)
