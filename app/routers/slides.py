import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.models.conversion import Conversion
from app.models.slide import Slide
from app.models.user import User
from app.schemas.slide import SlidePatch, SlideOut

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
    if body.speaker_notes is not None:
        updates["speaker_notes"] = body.speaker_notes
    if body.layout is not None:
        updates["layout"] = body.layout

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
        params = {k: v for k, v in updates.items()}
        params["id"] = str(sid)
        if "bullets" in params:
            import json
            params["bullets"] = json.dumps(params["bullets"])
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
