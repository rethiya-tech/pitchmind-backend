# Backend — Claude Code Intelligence

## Stack
Python 3.12, FastAPI async, PostgreSQL 15, SQLAlchemy 2.x async,
asyncpg, Alembic, Redis (Upstash), anthropic SDK (claude-sonnet-4),
python-pptx, pdfplumber, python-docx, pymupdf, markdown-it-py,
PyJWT, bcrypt, slowapi, google-cloud-storage, Jinja2, tenacity

## FastAPI conventions
- All route handlers: async def
- All dependencies injected via Depends()
- Return typed Pydantic v2 response schemas always
- Raise HTTPException with detail as dict, never plain string
- Router prefix pattern: /api/v1/{resource}
- Apply Depends(get_current_user) or Depends(require_admin) on every
  protected route — never leave an endpoint unprotected

## SQLAlchemy 2.x async pattern
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_user(db: AsyncSession, user_id: str):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()
```

## Auth dependencies (copy exactly)
```python
# app/dependencies/auth.py
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from app.core.security import decode_access_token
from app.models.user import User
from app.dependencies.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or expired token"})
    user = await db.get(User, payload["user_id"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401,
            detail={"code": "USER_INACTIVE", "message": "User not found or suspended"})
    return user

async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403,
            detail={"code": "FORBIDDEN", "message": "Admin access required"})
    return user
```

## Claude API pattern (use tenacity for retry)
```python
from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential
import json

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=1, min=2, max=8))
async def call_claude(system: str, user_message: str) -> dict:
    response = await client.messages.create(
        model="claude-sonnet-4",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_message}]
    )
    text = response.content[0].text.strip()
    # Always strip markdown fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    result = json.loads(text)
    return result, response.usage.input_tokens + response.usage.output_tokens
```

## GCS service pattern
```python
from google.cloud import storage
from datetime import timedelta

def get_client():
    if settings.GCS_CREDENTIALS_JSON:
        return storage.Client.from_service_account_json(
            settings.GCS_CREDENTIALS_JSON,
            project=settings.GCS_PROJECT_ID)
    return storage.Client(project=settings.GCS_PROJECT_ID)

def presign_upload(gcs_key: str, content_type: str) -> str:
    client = get_client()
    blob = client.bucket(settings.GCS_BUCKET).blob(gcs_key)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=15),
        method="PUT",
        content_type=content_type)

def presign_download(gcs_key: str, hours: int = 1) -> str:
    client = get_client()
    blob = client.bucket(settings.GCS_BUCKET).blob(gcs_key)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=hours),
        method="GET")

def upload_bytes(gcs_key: str, data: bytes,
                 content_type: str = "application/octet-stream") -> None:
    client = get_client()
    blob = client.bucket(settings.GCS_BUCKET).blob(gcs_key)
    blob.upload_from_string(data, content_type=content_type)

def blob_exists(gcs_key: str) -> bool:
    client = get_client()
    return client.bucket(settings.GCS_BUCKET).blob(gcs_key).exists()
```

## SSE streaming pattern
```python
from fastapi.responses import StreamingResponse
import asyncio, json

async def slide_generator(conversion_id: str, db: AsyncSession):
    try:
        slides = await get_pending_slides(db, conversion_id)
        total = len(slides)
        for i, slide_data in enumerate(slides):
            yield f"event: slide_start\ndata: {json.dumps({'index':i,'total':total})}\n\n"
            saved = await save_slide(db, conversion_id, i, slide_data)
            yield f"event: slide_done\ndata: {json.dumps({'slide':saved})}\n\n"
            yield f"event: progress\ndata: {json.dumps({'completed':i+1,'total':total})}\n\n"
            status = await get_status(db, conversion_id)
            if status == "cancelled":
                break
        yield f"event: done\ndata: {json.dumps({'conversion_id':conversion_id,'total_slides':i+1})}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message':str(e),'last_index':i})}\n\n"

@router.get("/{id}/stream")
async def stream(id: str, token: str, db=Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(401)
    return StreamingResponse(slide_generator(id, db),
        media_type="text/event-stream",
        headers={"Cache-Control":"no-cache,no-store",
                 "Connection":"keep-alive",
                 "X-Accel-Buffering":"no"})
```

## Testing conventions
- All test files in tests/
- pytest.ini: asyncio_mode = "auto"
- Mock Claude API with pytest-mock — NEVER call real API in tests
- Use httpx.AsyncClient(app=app, base_url="http://test") for routes
- Fixtures in conftest.py: test_db, test_client, test_user, test_admin
- Unit tests: pure functions, no DB, no external services
- Integration tests: test full HTTP request/response cycle with test DB
- Always assert both success and failure cases

## Alembic rules
- Single migration file: 001_initial_schema.py — all tables
- Never edit a migration after alembic upgrade head has been run
- Test: alembic upgrade head then alembic downgrade -1 before commit

## GCS bucket setup (do once in GCP Console)
1. Create bucket: pitchmind-files (region: us-central1)
2. Create service account with role: Storage Object Admin
3. Download JSON key → set GCS_CREDENTIALS_JSON path in env
4. Set CORS:
   gsutil cors set cors.json gs://pitchmind-files
   cors.json: [{"origin":["https://your-app.vercel.app"],
                "method":["PUT","GET"],"maxAgeSeconds":3600}]

## Docker development workflow
NOTE: docker-compose.yml lives in pitchmind-backend/ only.
The frontend runs locally with npm run dev — no Docker needed for it.

### Start all services
```bash
cp .env.example .env
docker compose up -d db redis
docker compose run --rm migrate
docker compose up backend
```

### Useful commands
```bash
docker compose logs -f backend
docker compose exec backend pytest tests/ -v --asyncio-mode=auto
docker compose exec db psql -U pitchmind
docker compose build backend
docker compose down
docker compose down -v
```

### Railway deployment
Railway auto-detects Dockerfile in repo root.
Set all env vars in Railway dashboard → Variables.
Migration must run manually once after first deploy:
  railway run alembic upgrade head
