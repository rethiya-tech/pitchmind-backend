import asyncio
import json
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.models.conversion import Conversion
from app.models.slide import Slide
from app.models.upload import Upload
from app.models.user import User
from app.schemas.conversion import (
    CancelResponse,
    ConversionCreate,
    ConversionCreateResponse,
    ConversionDetail,
    ConversionListResponse,
    ConversionOut,
    SlideOut,
)
from app.services import claude, themes as theme_svc
from app.services.audit import log_event

router = APIRouter(prefix="/conversions", tags=["conversions"])


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Conversion not found"})


async def _get_conversion_for_user(
    conv_id: uuid.UUID, user: User, db: AsyncSession
) -> Conversion:
    conv = await db.get(Conversion, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Conversion not found"})
    return conv


@router.post("", status_code=201, response_model=ConversionCreateResponse)
async def create_conversion(
    body: ConversionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify upload exists and belongs to user
    upload = await db.get(Upload, body.upload_id)
    if not upload or upload.user_id != current_user.id:
        raise HTTPException(status_code=404, detail={"code": "UPLOAD_NOT_FOUND", "message": "Upload not found"})

    # Create conversion record
    conv = Conversion(
        id=uuid.uuid4(),
        user_id=current_user.id,
        upload_id=body.upload_id,
        original_filename=upload.original_filename,
        status="pending",
        style=body.style,
        slide_count=body.slide_count,
        theme=body.theme,
        audience_level=body.audience_level,
        speaker_notes=body.speaker_notes,
    )
    db.add(conv)
    await db.flush()

    # Build document text for Claude
    # If the upload was not parsed yet (confirm didn't parse), do it now from the raw file
    if not upload.parsed_doc and not upload.parsed_preview:
        from app.services.parser import parse_bytes
        from app.services import gcs as _gcs
        settings = get_settings()
        try:
            if _gcs.is_configured():
                file_bytes = _gcs.download_bytes(settings.GCS_BUCKET, upload.gcs_key)
            else:
                file_path = _gcs.local_upload_path(str(upload.id))
                file_bytes = file_path.read_bytes()
            parsed = parse_bytes(file_bytes, upload.mime_type)
            # Save parsed content back using ORM to avoid asyncpg ::jsonb cast issues
            await db.execute(
                sa.update(Upload).where(Upload.id == upload.id).values(
                    parsed_doc=parsed.to_dict(),
                    parsed_preview=parsed.preview(max_words=500),
                )
            )
            upload.parsed_doc = parsed.to_dict()
            upload.parsed_preview = parsed.preview(max_words=500)
        except Exception as parse_err:
            # Roll back only the parsing update so the rest of the transaction continues
            await db.rollback()
            # Re-add the conversion that was flushed before the rollback
            db.add(conv)
            await db.flush()

    doc_text = ""
    if upload.parsed_doc:
        from app.services.parser import ParsedDocument
        doc = ParsedDocument.from_dict(upload.parsed_doc)
        doc_text = doc.to_prompt_text()
    elif upload.parsed_preview:
        doc_text = upload.parsed_preview
    else:
        doc_text = f"Document: {upload.original_filename}\n\nPlease generate a {body.slide_count}-slide presentation."

    # Call Claude and save slides
    try:
        system_prompt = claude.build_system_prompt(
            style=body.style,
            audience_level=body.audience_level,
            slide_count=body.slide_count,
        )
        raw_response, tokens_used = await claude.call_claude(system_prompt, doc_text)
        validated = claude.validate_slides(raw_response)

        # Save slides
        for i, slide_data in enumerate(validated):
            slide = Slide(
                id=uuid.uuid4(),
                conversion_id=conv.id,
                position=i,
                layout=slide_data.get("layout", "bullets"),
                title=slide_data.get("title", ""),
                bullets=slide_data.get("bullets", []),
                speaker_notes=slide_data.get("speaker_notes", ""),
                is_deleted=False,
            )
            db.add(slide)

        await db.execute(
            sa.text(
                "UPDATE conversions SET status='done', tokens_used=:tokens, "
                "completed_at=:completed, slide_count=:sc WHERE id=:id"
            ),
            {
                "tokens": tokens_used,
                "completed": datetime.now(timezone.utc),
                "sc": len(validated),
                "id": str(conv.id),
            },
        )
        await log_event(db, "conversion.created", actor_id=current_user.id, target_type="conversion", target_id=conv.id,
                        metadata={"filename": conv.original_filename, "slides": len(validated), "theme": body.theme})
        await db.flush()

    except Exception as exc:
        await db.execute(
            sa.text("UPDATE conversions SET status='failed', error_message=:msg WHERE id=:id"),
            {"msg": str(exc)[:500], "id": str(conv.id)},
        )
        await log_event(db, "conversion.failed", actor_id=current_user.id, target_type="conversion", target_id=conv.id,
                        metadata={"filename": conv.original_filename, "error": str(exc)[:200]})
        await db.flush()

    return ConversionCreateResponse(
        id=conv.id,
        status="pending",
        estimated_slides=body.slide_count,
        estimated_seconds=body.slide_count * 3,
    )


@router.get("", response_model=ConversionListResponse)
async def list_conversions(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    is_admin = current_user.role == "admin"

    if is_admin:
        total_result = await db.execute(sa.text("SELECT COUNT(*) FROM conversions"))
        total = total_result.scalar() or 0
        result = await db.execute(
            sa.select(Conversion)
            .order_by(Conversion.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
    else:
        total_result = await db.execute(
            sa.text("SELECT COUNT(*) FROM conversions WHERE user_id = :uid"),
            {"uid": str(current_user.id)},
        )
        total = total_result.scalar() or 0
        result = await db.execute(
            sa.select(Conversion)
            .where(Conversion.user_id == current_user.id)
            .order_by(Conversion.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

    convs = result.scalars().all()
    return ConversionListResponse(
        items=[ConversionOut.model_validate(c) for c in convs],
        total=total,
    )


@router.get("/{conversion_id}", response_model=ConversionDetail)
async def get_conversion(
    conversion_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cid = _parse_uuid(conversion_id)
    conv = await _get_conversion_for_user(cid, current_user, db)

    result = await db.execute(
        sa.select(Slide)
        .where(Slide.conversion_id == cid, Slide.is_deleted == False)
        .order_by(Slide.position)
    )
    slides = result.scalars().all()

    detail = ConversionDetail.model_validate(conv)
    detail.slides = [SlideOut.model_validate(s) for s in slides]
    return detail


@router.get("/{conversion_id}/slides")
async def list_slides(
    conversion_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cid = _parse_uuid(conversion_id)
    await _get_conversion_for_user(cid, current_user, db)
    result = await db.execute(
        sa.select(Slide)
        .where(Slide.conversion_id == cid, Slide.is_deleted == False)
        .order_by(Slide.position)
    )
    slides = result.scalars().all()
    from app.schemas.slide import SlideOut as SlideSchemaOut
    return [SlideSchemaOut.model_validate(s) for s in slides]


@router.post("/{conversion_id}/slides", status_code=201)
async def insert_slide(
    conversion_id: str,
    body: "SlideInsertBody",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cid = _parse_uuid(conversion_id)
    await _get_conversion_for_user(cid, current_user, db)

    # Shift existing slides down at the target position
    await db.execute(
        sa.text(
            "UPDATE slides SET position = position + 1 "
            "WHERE conversion_id = :cid AND position >= :pos AND is_deleted = false"
        ),
        {"cid": str(cid), "pos": body.position},
    )

    slide = Slide(
        id=uuid.uuid4(),
        conversion_id=cid,
        position=body.position,
        layout=body.layout,
        title=body.title,
        bullets=body.bullets,
        speaker_notes=body.speaker_notes,
        is_deleted=False,
    )
    db.add(slide)
    await db.flush()

    from app.schemas.slide import SlideOut as SlideSchemaOut
    return SlideSchemaOut.model_validate(slide)


@router.post("/{conversion_id}/slides/reorder")
async def reorder_slides(
    conversion_id: str,
    body: "SlideReorderBody",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cid = _parse_uuid(conversion_id)
    await _get_conversion_for_user(cid, current_user, db)
    for i, slide_id in enumerate(body.slide_ids):
        await db.execute(
            sa.text(
                "UPDATE slides SET position = :pos "
                "WHERE id = :id AND conversion_id = :cid"
            ),
            {"pos": i, "id": str(slide_id), "cid": str(cid)},
        )
    return {"success": True}


@router.post("/{conversion_id}/cancel", response_model=CancelResponse)
async def cancel_conversion(
    conversion_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cid = _parse_uuid(conversion_id)
    conv = await _get_conversion_for_user(cid, current_user, db)
    if conv.status not in ("pending", "generating"):
        raise HTTPException(status_code=409, detail={"code": "NOT_CANCELLABLE", "message": "Conversion cannot be cancelled"})

    result = await db.execute(
        sa.text("SELECT COUNT(*) FROM slides WHERE conversion_id = :cid AND is_deleted = false"),
        {"cid": str(cid)},
    )
    slides_completed = result.scalar() or 0

    await db.execute(
        sa.text("UPDATE conversions SET status='cancelled' WHERE id=:id"),
        {"id": str(cid)},
    )
    return CancelResponse(message="Cancelled", slides_completed=slides_completed)


@router.delete("/{conversion_id}", status_code=204)
async def delete_conversion(
    conversion_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cid = _parse_uuid(conversion_id)
    # Admins can delete any conversion; regular users only their own
    if current_user.role == "admin":
        conv = await db.get(Conversion, cid)
        if not conv:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Conversion not found"})
    else:
        conv = await _get_conversion_for_user(cid, current_user, db)

    await db.execute(
        sa.text("DELETE FROM slides WHERE conversion_id = :cid"),
        {"cid": str(cid)},
    )
    await db.execute(
        sa.text("DELETE FROM conversions WHERE id = :id"),
        {"id": str(cid)},
    )
    await log_event(db, "conversion.deleted", actor_id=current_user.id, target_type="conversion", target_id=cid,
                    metadata={"filename": conv.original_filename})


@router.get("/{conversion_id}/stream")
async def stream_conversion(
    conversion_id: str,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if not token:
        raise HTTPException(status_code=401, detail={"code": "NO_TOKEN", "message": "Token required"})

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Invalid token"})

    user_id = payload.get("user_id")
    user = await db.get(User, uuid.UUID(str(user_id))) if user_id else None
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Invalid token"})

    conv = await db.get(Conversion, conversion_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Conversion not found"})

    async def event_generator():
        result = await db.execute(
            sa.select(Slide)
            .where(Slide.conversion_id == conversion_id, Slide.is_deleted == False)
            .order_by(Slide.position)
        )
        slides = result.scalars().all()
        total = len(slides)

        for i, slide in enumerate(slides):
            yield f"event: slide_start\ndata: {json.dumps({'index': i, 'total': total})}\n\n"
            slide_data = {
                "id": str(slide.id),
                "position": slide.position,
                "layout": slide.layout,
                "title": slide.title,
                "bullets": slide.bullets,
                "speaker_notes": slide.speaker_notes,
            }
            yield f"event: slide_done\ndata: {json.dumps({'slide': slide_data})}\n\n"
            yield f"event: progress\ndata: {json.dumps({'completed': i + 1, 'total': total})}\n\n"
            await asyncio.sleep(0)

        # Mark as done
        await db.execute(
            sa.text("UPDATE conversions SET status='done', completed_at=NOW() WHERE id=:id AND status != 'done'"),
            {"id": str(conversion_id)},
        )
        yield f"event: done\ndata: {json.dumps({'conversion_id': str(conversion_id), 'total_slides': total})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Request body models for type annotations above
from pydantic import BaseModel  # noqa: E402


class SlideInsertBody(BaseModel):
    position: int = 0
    title: str = ""
    bullets: list[str] = []
    speaker_notes: str = ""
    layout: str = "bullets"


class SlideReorderBody(BaseModel):
    slide_ids: list[uuid.UUID]
