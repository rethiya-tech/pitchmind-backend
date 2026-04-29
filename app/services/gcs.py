import uuid
from datetime import timedelta
from pathlib import Path

from google.cloud import storage

from app.core.config import get_settings


def _get_client() -> storage.Client:
    settings = get_settings()
    if settings.GCS_CREDENTIALS_JSON:
        import json as _json
        raw = settings.GCS_CREDENTIALS_JSON.strip()
        if raw.startswith("{"):
            info = _json.loads(raw)
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(info)
            return storage.Client(credentials=creds, project=settings.GCS_PROJECT_ID)
        return storage.Client.from_service_account_json(raw, project=settings.GCS_PROJECT_ID)
    return storage.Client()


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.GCS_BUCKET and settings.GCS_PROJECT_ID)


def generate_upload_key(user_id: str, filename: str) -> str:
    return f"uploads/{user_id}/{uuid.uuid4().hex}-{filename}"


def generate_pptx_key(conversion_id: str) -> str:
    return f"exports/{conversion_id}.pptx"


def get_signed_upload_url(
    bucket: str,
    key: str,
    content_type: str = "application/octet-stream",
    expiry_minutes: int = 15,
) -> str:
    client = _get_client()
    blob = client.bucket(bucket).blob(key)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expiry_minutes),
        method="PUT",
        content_type=content_type,
    )


def get_signed_download_url(
    bucket: str,
    key: str,
    expiry_hours: int = 1,
) -> str:
    client = _get_client()
    blob = client.bucket(bucket).blob(key)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=expiry_hours),
        method="GET",
    )


def upload_bytes(
    bucket: str,
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> None:
    client = _get_client()
    blob = client.bucket(bucket).blob(key)
    blob.upload_from_string(data, content_type=content_type)


def blob_exists(bucket: str, key: str) -> bool:
    client = _get_client()
    return client.bucket(bucket).blob(key).exists()


# Local dev storage helpers — used when GCS is not configured

LOCAL_UPLOAD_DIR = Path("local_uploads")


def local_upload_path(upload_id: str) -> Path:
    LOCAL_UPLOAD_DIR.mkdir(exist_ok=True)
    return LOCAL_UPLOAD_DIR / upload_id


def local_blob_exists(upload_id: str) -> bool:
    return local_upload_path(upload_id).exists()
