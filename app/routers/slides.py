import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.models.conversion import Conversion
from app.models.slide import Slide
from app.models.user import User
from app.schemas.slide import SlidePatch, SlideOut
from app.services import gcs

router = APIRouter(prefix="/slides", tags=["slides"])


def _parse_slide_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Slide not found"})


async def _get_slide_for_user(
    slide_id: uuid.UUID, user: User, db: AsyncSession
) -> Slide:
    slide = await db.get(Slide, slide_id)
    if not slide:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Slide not found"})

    # Verify ownership through conversion
    conv = await db.get(Conversion, slide.conversion_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Access denied"})
    return slide


@router.patch("/{slide_id}", response_model=SlideOut)
async def patch_slide(
    slide_id: str,
    body: SlidePatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _parse_slide_uuid(slide_id)
    slide = await _get_slide_for_user(sid, current_user, db)

    updates: dict = {}
    if body.title is not None:
        updates["title"] = body.title
    if body.bullets is not None:
        updates["bullets"] = body.bullets
    if body.text_styles is not None:
        updates["text_styles"] = body.text_styles
    if body.speaker_notes is not None:
        updates["speaker_notes"] = body.speaker_notes
    if body.layout is not None:
        updates["layout"] = body.layout
    if body.color_scheme is not None:
        updates["color_scheme"] = body.color_scheme
    if body.shape_style is not None:
        updates["shape_style"] = body.shape_style
    if body.background_image_url is not None:
        updates["background_image_url"] = body.background_image_url

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
        params = {k: v for k, v in updates.items()}
        params["id"] = str(sid)
        if "bullets" in params:
            import json
            params["bullets"] = json.dumps(params["bullets"])
        if "text_styles" in params:
            import json
            params["text_styles"] = json.dumps(params["text_styles"])
        await db.execute(
            sa.text(f"UPDATE slides SET {set_clauses} WHERE id = :id"),
            params,
        )
        await db.flush()
        await db.refresh(slide)

    return SlideOut.model_validate(slide)


@router.delete("/{slide_id}", response_model=SlideOut)
async def delete_slide(
    slide_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _parse_slide_uuid(slide_id)
    slide = await _get_slide_for_user(sid, current_user, db)
    now = datetime.now(timezone.utc)
    await db.execute(
        sa.text("UPDATE slides SET is_deleted = true, deleted_at = :now, updated_at = :now WHERE id = :id"),
        {"now": now, "id": str(sid)},
    )
    await db.execute(
        sa.text(
            "UPDATE conversions SET slide_count = ("
            "  SELECT COUNT(*) FROM slides WHERE conversion_id = :cid AND is_deleted = false"
            ") WHERE id = :cid"
        ),
        {"cid": str(slide.conversion_id)},
    )
    await db.flush()
    await db.refresh(slide)
    return SlideOut.model_validate(slide)


class SlideEnhanceBody(BaseModel):
    instruction: str


@router.post("/{slide_id}/ai-enhance")
async def ai_enhance_slide(
    slide_id: str,
    body: SlideEnhanceBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _parse_slide_uuid(slide_id)
    slide = await _get_slide_for_user(sid, current_user, db)

    import logging
    _log = logging.getLogger(__name__)
    from app.services.claude import enhance_slide, friendly_error
    try:
        result = await enhance_slide(
            body.instruction,
            {
                "title": slide.title,
                "bullets": slide.bullets,
                "speaker_notes": slide.speaker_notes,
                "layout": slide.layout,
                "color_scheme": slide.color_scheme,
                "shape_style": slide.shape_style,
            },
        )
    except Exception as exc:
        _log.error("ai-enhance error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail={"code": "AI_ERROR", "message": friendly_error(exc)},
        )
    return result


_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB


@router.post("/{slide_id}/upload-image")
async def upload_slide_image(
    slide_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _parse_slide_uuid(slide_id)
    slide = await _get_slide_for_user(sid, current_user, db)

    content_type = file.content_type or "image/jpeg"
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail={"code": "INVALID_TYPE", "message": "Only JPEG, PNG, WebP, and GIF images are allowed"})

    data = await file.read()
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail={"code": "FILE_TOO_LARGE", "message": "Image must be under 8 MB"})

    settings = get_settings()
    gcs_key = f"slide-images/{slide_id}"

    if gcs.is_configured():
        gcs.upload_bytes(settings.GCS_BUCKET, gcs_key, data, content_type)
    else:
        gcs.LOCAL_UPLOAD_DIR.mkdir(exist_ok=True)
        (gcs.LOCAL_UPLOAD_DIR / f"slide_image_{slide_id}").write_bytes(data)

    if settings.BACKEND_URL:
        base = settings.BACKEND_URL.rstrip("/")
    else:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        base = f"{proto}://{host}" if host else str(request.base_url).rstrip("/")

    image_url = f"{base}/api/v1/slides/{slide_id}/image"
    now = datetime.now(timezone.utc)
    await db.execute(
        sa.text("UPDATE slides SET background_image_url = :url, updated_at = :now WHERE id = :id"),
        {"url": image_url, "now": now, "id": str(sid)},
    )
    await db.flush()
    await db.refresh(slide)

    return {"image_url": image_url}


@router.get("/{slide_id}/image", include_in_schema=False)
async def serve_slide_image(
    slide_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        sid = uuid.UUID(slide_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Not found"})

    slide = await db.get(Slide, sid)
    if not slide or not slide.background_image_url:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "No image for this slide"})

    settings = get_settings()
    gcs_key = f"slide-images/{slide_id}"

    if gcs.is_configured():
        try:
            data = gcs.download_bytes(settings.GCS_BUCKET, gcs_key)
        except Exception:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Image not found in storage"})
    else:
        local_path = gcs.LOCAL_UPLOAD_DIR / f"slide_image_{slide_id}"
        if not local_path.exists():
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Image not found"})
        data = local_path.read_bytes()

    content_type = "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        content_type = "image/png"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        content_type = "image/webp"
    elif data[:6] in (b"GIF87a", b"GIF89a"):
        content_type = "image/gif"

    return Response(content=data, media_type=content_type, headers={"Cache-Control": "public, max-age=31536000"})


@router.post("/{slide_id}/restore", response_model=SlideOut)
async def restore_slide(
    slide_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sid = _parse_slide_uuid(slide_id)
    slide = await _get_slide_for_user(sid, current_user, db)
    now = datetime.now(timezone.utc)
    await db.execute(
        sa.text("UPDATE slides SET is_deleted = false, deleted_at = NULL, updated_at = :now WHERE id = :id"),
        {"now": now, "id": str(sid)},
    )
    await db.execute(
        sa.text(
            "UPDATE conversions SET slide_count = ("
            "  SELECT COUNT(*) FROM slides WHERE conversion_id = :cid AND is_deleted = false"
            ") WHERE id = :cid"
        ),
        {"cid": str(slide.conversion_id)},
    )
    await db.flush()
    await db.refresh(slide)
    return SlideOut.model_validate(slide)
