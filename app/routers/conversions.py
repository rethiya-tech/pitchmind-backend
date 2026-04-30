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
from app.services import claude
from app.services.audit import log_event

router = APIRouter(prefix="/conversions", tags=["conversions"])

PPTX_MIMES = {
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
}


async def _db_exec(sql: str, params: dict) -> None:
    """Run a single SQL statement in its own short-lived DB session."""
    from app.core.database import get_session_factory
    factory = get_session_factory()
    async with factory() as db:
        await db.execute(sa.text(sql), params)
        await db.commit()


async def _generate_slides_task(
    conv_id: uuid.UUID,
    doc_text: str,
    pptx_slides: list[dict] | None,
    style: str,
    audience_level: str,
    slide_count: int,
    theme: str,
    original_filename: str,
    user_id: uuid.UUID,
) -> None:
    """Background task: calls AI and saves slides, then marks conversion done/failed.

    DB connections are held only during actual writes — never during the AI call —
    so the connection pool is not exhausted while waiting for the AI API.
    """
    from app.services.claude import friendly_error

    try:
        # 1. Mark as generating (brief DB write, connection released immediately)
        await _db_exec(
            "UPDATE conversions SET status='generating' WHERE id=:id",
            {"id": str(conv_id)},
        )

        # 2. Call AI — NO DB connection held during this (may take 30-120s)
        if pptx_slides is not None:
            validated = pptx_slides
            tokens_used = 0
        else:
            system_prompt = claude.build_system_prompt(
                style=style,
                audience_level=audience_level,
                slide_count=slide_count,
            )
            raw_response, tokens_used = await claude.call_claude(system_prompt, doc_text)
            validated = claude.validate_slides(raw_response)

        validated.append({
            "layout": "hero",
            "title": "Thank You",
            "bullets": ["Questions & Discussion"],
            "speaker_notes": "Thank the audience for their time and attention. Open the floor for questions and discussion.",
            "color_scheme": "default",
            "shape_style": "square",
        })

        # 3. Save each slide individually (each gets its own short DB session)
        from app.core.database import get_session_factory
        factory = get_session_factory()
        for i, slide_data in enumerate(validated):
            async with factory() as db:
                slide = Slide(
                    id=uuid.uuid4(),
                    conversion_id=conv_id,
                    position=i,
                    layout=slide_data.get("layout", "bullets"),
                    title=slide_data.get("title", ""),
                    bullets=slide_data.get("bullets", []),
                    speaker_notes=slide_data.get("speaker_notes", ""),
                    color_scheme=slide_data.get("color_scheme", "default"),
                    shape_style=slide_data.get("shape_style", "square"),
                    is_deleted=False,
                )
                db.add(slide)
                await db.commit()

        # 4. Mark as done (brief DB write)
        presentation_name = validated[0].get("title", "").strip() if validated else ""
        await _db_exec(
            "UPDATE conversions SET status='done', tokens_used=:tokens, "
            "completed_at=:completed, slide_count=:sc, name=:name WHERE id=:id",
            {
                "tokens": tokens_used,
                "completed": datetime.now(timezone.utc),
                "sc": len(validated),
                "name": presentation_name or None,
                "id": str(conv_id),
            },
        )

    except Exception as exc:
        try:
            await _db_exec(
                "UPDATE conversions SET status='failed', error_message=:msg WHERE id=:id",
                {"msg": friendly_error(exc), "id": str(conv_id)},
            )
        except Exception:
            pass


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
    upload = None
    doc_text: str = ""
    pptx_slides: list[dict] | None = None

    # ── Prompt-only mode ──────────────────────────────────────────────────────
    if body.prompt_text and not body.upload_id:
        display_name = (body.prompt_text[:57] + "…") if len(body.prompt_text) > 57 else body.prompt_text
        conv = Conversion(
            id=uuid.uuid4(),
            user_id=current_user.id,
            upload_id=None,
            original_filename=display_name,
            status="pending",
            style=body.style,
            slide_count=body.slide_count,
            theme=body.theme,
            audience_level=body.audience_level,
            speaker_notes=body.speaker_notes,
        )
        db.add(conv)
        doc_text = body.prompt_text

    # ── File upload mode ──────────────────────────────────────────────────────
    else:
        upload = await db.get(Upload, body.upload_id)
        if not upload or upload.user_id != current_user.id:
            raise HTTPException(status_code=404, detail={"code": "UPLOAD_NOT_FOUND", "message": "Upload not found"})

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

        # Parse document if not already done (fast, happens before returning)
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
                await db.execute(
                    sa.update(Upload).where(Upload.id == upload.id).values(
                        parsed_doc=parsed.to_dict(),
                        parsed_preview=parsed.preview(max_words=500),
                    )
                )
                upload.parsed_doc = parsed.to_dict()
                upload.parsed_preview = parsed.preview(max_words=500)
            except Exception:
                await db.rollback()
                db.add(conv)
                upload = await db.get(Upload, body.upload_id)

        if upload and upload.parsed_doc:
            from app.services.parser import ParsedDocument
            doc = ParsedDocument.from_dict(upload.parsed_doc)
            doc_text = doc.to_prompt_text()
        elif upload and upload.parsed_preview:
            doc_text = upload.parsed_preview
        else:
            doc_text = f"Document: {upload.original_filename}\n\nPlease generate a {body.slide_count}-slide presentation."

        # For PPTX uploads with clear slide structure, extract directly
        if upload.mime_type in PPTX_MIMES and upload.parsed_doc:
            from app.services.parser import ParsedDocument
            _doc = ParsedDocument.from_dict(upload.parsed_doc)
            _has_real = any(
                s.heading and not s.heading.startswith("Slide ") and s.heading != "Presentation"
                for s in _doc.sections
            )
            if _has_real:
                pptx_slides = []
                for s in _doc.sections:
                    bullets = (s.bullets or s.paragraphs)[:6]
                    while len(bullets) < 3:
                        bullets.append("")
                    pptx_slides.append({
                        "layout": "bullets",
                        "title": s.heading,
                        "bullets": bullets,
                        "speaker_notes": "",
                    })

    # Commit the conversion INSERT now so the background task can find the row.
    # get_db() would only commit after the handler returns, which is too late
    # since create_task() may start executing immediately on the next await.
    await db.commit()

    asyncio.create_task(_generate_slides_task(
        conv_id=conv.id,
        doc_text=doc_text,
        pptx_slides=pptx_slides,
        style=body.style,
        audience_level=body.audience_level,
        slide_count=body.slide_count,
        theme=body.theme,
        original_filename=conv.original_filename or "",
        user_id=current_user.id,
    ))

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
        color_scheme=body.color_scheme,
        shape_style=body.shape_style,
        is_deleted=False,
    )
    db.add(slide)
    await db.flush()

    await db.execute(
        sa.text(
            "UPDATE conversions SET slide_count = ("
            "  SELECT COUNT(*) FROM slides WHERE conversion_id = :cid AND is_deleted = false"
            ") WHERE id = :cid"
        ),
        {"cid": str(cid)},
    )

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

    cid = _parse_uuid(conversion_id)
    conv = await db.get(Conversion, cid)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Conversion not found"})

    async def event_generator():
        seen_positions: set[int] = set()
        slides_emitted = 0
        expected_total = 0
        max_wait_secs = 300
        start = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > max_wait_secs:
                yield f"event: error\ndata: {json.dumps({'message': 'Generation timed out'})}\n\n"
                return

            # Always query fresh from DB to avoid SQLAlchemy identity-map cache
            status_result = await db.execute(
                sa.text("SELECT status, error_message, slide_count FROM conversions WHERE id=:id"),
                {"id": str(cid)},
            )
            status_row = status_result.fetchone()
            if not status_row:
                yield f"event: error\ndata: {json.dumps({'message': 'Conversion not found'})}\n\n"
                return

            current_status = status_row[0]
            error_message = status_row[1]
            expected_total = status_row[2] or expected_total

            if current_status == "failed":
                yield f"event: error\ndata: {json.dumps({'message': error_message or 'Generation failed'})}\n\n"
                return

            if current_status == "cancelled":
                yield f"event: error\ndata: {json.dumps({'message': 'Generation was cancelled'})}\n\n"
                return

            # Fetch any new slides not yet sent
            slides_result = await db.execute(
                sa.text(
                    "SELECT id, position, layout, title, bullets, speaker_notes, color_scheme, shape_style "
                    "FROM slides WHERE conversion_id=:cid AND is_deleted=false ORDER BY position"
                ),
                {"cid": str(cid)},
            )
            all_slides = slides_result.fetchall()
            total_so_far = len(all_slides)

            for row in all_slides:
                pos = row[1]
                if pos not in seen_positions:
                    seen_positions.add(pos)
                    slides_emitted += 1
                    slide_data = {
                        "id": str(row[0]),
                        "position": pos,
                        "layout": row[2],
                        "title": row[3],
                        "bullets": row[4] if isinstance(row[4], list) else [],
                        "speaker_notes": row[5] or "",
                        "color_scheme": row[6] or "default",
                        "shape_style": row[7] or "square",
                    }
                    yield f"event: slide_start\ndata: {json.dumps({'index': pos, 'total': expected_total or total_so_far})}\n\n"
                    yield f"event: slide_done\ndata: {json.dumps({'slide': slide_data})}\n\n"
                    yield f"event: progress\ndata: {json.dumps({'completed': slides_emitted, 'total': expected_total or total_so_far})}\n\n"

            if current_status == "done":
                yield f"event: done\ndata: {json.dumps({'conversion_id': str(cid), 'total_slides': total_so_far})}\n\n"
                return

            # Still generating — wait before next poll
            await asyncio.sleep(1.5)

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
    color_scheme: str = "default"
    shape_style: str = "square"


class SlideReorderBody(BaseModel):
    slide_ids: list[uuid.UUID]
