import io
import json
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.db import get_db
from app.models.conversion import Conversion
from app.models.slide import Slide
from app.models.template import Template
from app.models.user import User
from app.schemas.template import TemplateCopyResponse, TemplateDetail, TemplateListResponse, TemplateOut
from app.services.audit import log_event
from app.services import gcs as _gcs

router = APIRouter(prefix="/templates", tags=["templates"])

ALLOWED_MIME = {
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
}


def _parse_pptx_slides(file_bytes: bytes) -> tuple[list[dict], str | None]:
    """Extract slide titles and bullet text from a .pptx file.
    Returns (slides, warning_message). On parse failure returns ([], error_str)."""
    try:
        from pptx import Presentation
        from pptx.enum.shapes import PP_PLACEHOLDER
        prs = Presentation(io.BytesIO(file_bytes))

        # Get slide count from XML directly — reliable even for exotic PPTX
        try:
            raw_count = len(prs.slides._sldIdLst)
        except Exception:
            raw_count = 0

        slides = []
        parse_errors = []

        for i in range(raw_count):
            title = ""
            bullets: list[str] = []
            try:
                slide = prs.slides[i]
                for shape in slide.shapes:
                    try:
                        if not shape.has_text_frame:
                            continue
                        text = shape.text_frame.text.strip()
                        if not text:
                            continue
                        # Detect title placeholder (idx=0 only)
                        is_title = (
                            hasattr(shape, "placeholder_format")
                            and shape.placeholder_format is not None
                            and shape.placeholder_format.idx == 0
                        )
                        if is_title and not title:
                            title = text
                        else:
                            for para in shape.text_frame.paragraphs:
                                line = para.text.strip()
                                if line and line != title:
                                    bullets.append(line)
                    except Exception:
                        continue
                # Speaker notes
                notes = ""
                try:
                    if slide.has_notes_slide:
                        notes = slide.notes_slide.notes_text_frame.text.strip()
                except Exception:
                    pass
            except Exception as e:
                parse_errors.append(str(e))

            slides.append({
                "position": i,
                "layout": "bullets",
                "title": title or f"Slide {i + 1}",
                "bullets": bullets[:8],
                "speaker_notes": notes if 'notes' in dir() else "",
            })

        warning = f"Some slides had parse errors: {'; '.join(parse_errors)}" if parse_errors else None
        return slides, warning
    except Exception as e:
        return [], str(e)


# ── Admin: upload a template ──────────────────────────────────────────────────

@router.post("", status_code=201, response_model=TemplateOut)
async def upload_template(
    name: str = Form(...),
    description: str = Form(""),
    theme: str = Form("clean_slate"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if file.content_type not in ALLOWED_MIME and not (file.filename or "").endswith(".pptx"):
        raise HTTPException(status_code=415, detail={"code": "INVALID_TYPE", "message": "Only .pptx files are accepted"})

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_FILE", "message": "Uploaded file is empty"})
    slides, parse_warning = _parse_pptx_slides(file_bytes)

    # Store the raw file
    template_id = uuid.uuid4()
    gcs_key = f"templates/{template_id}.pptx"

    if _gcs.is_configured():
        from app.core.config import get_settings
        settings = get_settings()
        _gcs.upload_bytes(gcs_key, file_bytes, content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
    else:
        local_path = _gcs.LOCAL_UPLOAD_DIR / f"template_{template_id}.pptx"
        _gcs.LOCAL_UPLOAD_DIR.mkdir(exist_ok=True)
        local_path.write_bytes(file_bytes)

    template = Template(
        id=template_id,
        name=name,
        description=description or None,
        pptx_key=gcs_key,
        slide_count=len(slides),
        slides_json=slides,
        theme=theme,
        is_active=True,
        created_by=admin.id,
    )
    db.add(template)
    await log_event(db, "template.created", actor_id=admin.id, target_type="template", target_id=template_id,
                    metadata={"name": name, "slides": len(slides)})
    await db.commit()
    await db.refresh(template)
    out = TemplateOut.model_validate(template)
    if parse_warning:
        out.parse_warning = f"Slides could not be extracted ({parse_warning}). Template saved with 0 slides."
    return out


# ── List templates (all authenticated users) ──────────────────────────────────

@router.get("", response_model=TemplateListResponse)
async def list_templates(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    total_r = await db.execute(sa.text("SELECT COUNT(*) FROM templates WHERE is_active = true"))
    total = total_r.scalar() or 0

    result = await db.execute(
        sa.select(Template)
        .where(Template.is_active == True)
        .order_by(Template.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = result.scalars().all()
    return TemplateListResponse(items=[TemplateOut.model_validate(t) for t in items], total=total)


# ── Get template detail ────────────────────────────────────────────────────────

@router.get("/{template_id}", response_model=TemplateDetail)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        tid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Template not found"})

    t = await db.get(Template, tid)
    if not t or not t.is_active:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Template not found"})
    return TemplateDetail.model_validate(t)


# ── Copy a template → new conversion ─────────────────────────────────────────

@router.post("/{template_id}/copy", response_model=TemplateCopyResponse)
async def copy_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        tid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Template not found"})

    t = await db.get(Template, tid)
    if not t or not t.is_active:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Template not found"})

    slides_data = t.slides_json if isinstance(t.slides_json, list) else []
    slide_count = len(slides_data)

    # Check if template has real extractable content
    has_content = any(
        (s.get("title", "").strip() and not s.get("title", "").startswith("Slide "))
        or s.get("bullets")
        for s in slides_data
    )

    # For image-based templates with no text, generate a proper pitch deck structure
    if not has_content and slide_count > 0:
        from app.services import claude as claude_svc
        system = claude_svc.build_system_prompt("professional", "executive", slide_count)
        stub_raw, _ = claude_svc._stub_slides(system, slide_count)
        ai_slides = claude_svc.validate_slides(stub_raw)
        for i, ai_slide in enumerate(ai_slides[:slide_count]):
            if i < len(slides_data):
                slides_data[i]["title"] = ai_slide.get("title", "")
                slides_data[i]["bullets"] = ai_slide.get("bullets", [])
                slides_data[i]["speaker_notes"] = ai_slide.get("speaker_notes", "")
                slides_data[i]["layout"] = ai_slide.get("layout", "bullets")

    # Normalise any missing fields
    for i, s in enumerate(slides_data):
        if not s.get("title"):
            s["title"] = f"Slide {i + 1}"
        s.setdefault("bullets", [])
        s.setdefault("speaker_notes", "")
        s.setdefault("layout", "bullets")

    # Create conversion record
    conv_id = uuid.uuid4()
    await db.execute(
        sa.text(
            "INSERT INTO conversions (id, user_id, original_filename, status, theme, slide_count, completed_at) "
            "VALUES (:id, :uid, :fname, 'done', :theme, :sc, :now)"
        ),
        {
            "id": str(conv_id),
            "uid": str(current_user.id),
            "fname": f"{t.name}.pptx",
            "theme": t.theme or "clean_slate",
            "sc": slide_count,
            "now": datetime.now(timezone.utc),
        },
    )

    for slide_data in slides_data:
        await db.execute(
            sa.text(
                "INSERT INTO slides (id, conversion_id, position, layout, title, bullets, speaker_notes, is_deleted) "
                "VALUES (:id, :cid, :pos, :layout, :title, CAST(:bullets AS jsonb), :notes, false)"
            ),
            {
                "id": str(uuid.uuid4()),
                "cid": str(conv_id),
                "pos": slide_data.get("position", 0),
                "layout": slide_data.get("layout", "bullets"),
                "title": slide_data.get("title", ""),
                "bullets": json.dumps(slide_data.get("bullets", [])),
                "notes": slide_data.get("speaker_notes", ""),
            },
        )

    await log_event(db, "template.copied", actor_id=current_user.id, target_type="conversion", target_id=conv_id,
                    metadata={"template_id": str(tid), "template_name": t.name})
    await db.commit()

    return TemplateCopyResponse(conversion_id=conv_id, slide_count=slide_count)


# ── Admin: delete (deactivate) a template ─────────────────────────────────────

@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        tid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Template not found"})

    t = await db.get(Template, tid)
    if not t:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Template not found"})

    await db.execute(sa.text("UPDATE templates SET is_active = false WHERE id = :id"), {"id": str(tid)})
    await log_event(db, "template.deleted", actor_id=admin.id, target_type="template", target_id=tid,
                    metadata={"name": t.name})
    await db.commit()
