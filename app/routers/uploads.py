import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.models.upload import Upload
from app.models.user import User
from app.schemas.upload import (
    ConfirmResponse,
    PresignRequest,
    PresignResponse,
    PreviewResponse,
    UploadListResponse,
    UploadOut,
)
from app.services import gcs

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/presign", response_model=PresignResponse)
async def presign_upload(
    body: PresignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = get_settings()
    gcs_key = gcs.generate_upload_key(str(current_user.id), body.filename)

    upload = Upload(
        id=uuid.uuid4(),
        user_id=current_user.id,
        gcs_key=gcs_key,
        original_filename=body.filename,
        file_size_bytes=body.size_bytes,
        mime_type=body.content_type,
        parse_status="pending",
    )
    db.add(upload)
    await db.commit()  # commit before returning so local_upload can find the row immediately

    # Always route the PUT through the backend (avoids GCS CORS requirements).
    # Use explicit BACKEND_URL if set; otherwise reconstruct from forwarded headers
    # since request.base_url is the internal address behind Render/nginx proxies.
    if settings.BACKEND_URL:
        base = settings.BACKEND_URL.rstrip("/")
    else:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        base = f"{proto}://{host}" if host else str(request.base_url).rstrip("/")
    upload_url = f"{base}/api/v1/uploads/{upload.id}/local"

    return PresignResponse(
        upload_url=upload_url,
        gcs_key=gcs_key,
        upload_id=upload.id,
    )


@router.put("/{upload_id}/local", include_in_schema=False)
async def local_upload(
    upload_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accepts raw file body, stores locally or uploads to GCS if configured."""
    try:
        uid = uuid.UUID(upload_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Upload not found"})

    upload = await db.get(Upload, uid)
    if not upload or upload.user_id != current_user.id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Upload not found"})

    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_BODY", "message": "No file data received"})

    settings = get_settings()
    if gcs.is_configured():
        gcs.upload_bytes(settings.GCS_BUCKET, upload.gcs_key, data, upload.mime_type)
    else:
        gcs.local_upload_path(str(uid)).write_bytes(data)

    await db.execute(
        sa.text("UPDATE uploads SET parse_status='done' WHERE id=:id"),
        {"id": str(uid)},
    )

    return {"upload_id": str(uid), "status": "received"}


@router.post("/{upload_id}/confirm", response_model=ConfirmResponse)
async def confirm_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = get_settings()
    try:
        uid = uuid.UUID(upload_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Upload not found"})
    upload = await db.get(Upload, uid)
    if not upload or upload.user_id != current_user.id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Upload not found"})

    if gcs.is_configured():
        if not gcs.blob_exists(settings.GCS_BUCKET, upload.gcs_key):
            raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "File not found in storage"})
    else:
        if not gcs.local_blob_exists(upload_id):
            raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "File not found in local storage"})

    await db.execute(
        sa.text("UPDATE uploads SET parse_status = 'done' WHERE id = :id"),
        {"id": str(uid)},
    )
    await db.flush()

    return ConfirmResponse(upload_id=upload.id, parse_status="done")


@router.get("/{upload_id}/preview", response_model=PreviewResponse)
async def get_upload_preview(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        uid = uuid.UUID(upload_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Upload not found"})
    upload = await db.get(Upload, uid)
    if not upload or upload.user_id != current_user.id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Upload not found"})

    if upload.parsed_preview:
        words = upload.parsed_preview.split()
        return PreviewResponse(preview_text=upload.parsed_preview, word_count=len(words))

    if upload.parsed_doc:
        from app.services.parser import ParsedDocument
        doc = ParsedDocument.from_dict(upload.parsed_doc)
        preview = doc.preview(max_words=500)
        return PreviewResponse(preview_text=preview, word_count=doc.word_count)

    raise HTTPException(status_code=404, detail={"code": "NOT_PARSED", "message": "Document not yet parsed"})


@router.get("", response_model=UploadListResponse)
async def list_uploads(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    total_result = await db.execute(
        sa.text("SELECT COUNT(*) FROM uploads WHERE user_id = :uid"),
        {"uid": str(current_user.id)},
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        sa.select(Upload)
        .where(Upload.user_id == current_user.id)
        .order_by(Upload.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    uploads = result.scalars().all()
    return UploadListResponse(
        items=[UploadOut.model_validate(u) for u in uploads],
        total=total,
    )
