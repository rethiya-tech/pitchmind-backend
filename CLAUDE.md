# Backend — Claude Code Intelligence

## Stack
Python 3.12, FastAPI async, PostgreSQL 15, SQLAlchemy 2.x async,
asyncpg, Alembic, Redis (Upstash), anthropic SDK (claude-sonnet-4-5),
google-genai SDK (gemini-2.5-flash), python-pptx, pdfplumber,
python-docx, pymupdf, markdown-it-py, PyJWT, bcrypt, slowapi,
google-cloud-storage, Jinja2, tenacity

## Application Architecture

```
app/
├── main.py                  # FastAPI app + CORS + router registration
├── core/
│   ├── config.py            # Pydantic Settings (all env vars)
│   ├── database.py          # SQLAlchemy async engine + session factory
│   ├── security.py          # bcrypt hashing, JWT create/decode
│   └── redis.py             # async Redis client
├── dependencies/
│   ├── auth.py              # get_current_user(), require_admin()
│   └── db.py                # get_db() async session with auto-commit/rollback
├── models/                  # SQLAlchemy ORM models
│   ├── user.py
│   ├── conversion.py
│   ├── slide.py             # includes color_scheme + shape_style columns
│   ├── upload.py
│   ├── template.py
│   └── audit_log.py
├── schemas/                 # Pydantic v2 request/response schemas
│   ├── auth.py
│   ├── upload.py
│   ├── conversion.py
│   ├── slide.py             # SlidePatch includes color_scheme + shape_style
│   ├── template.py
│   └── admin.py
├── routers/                 # 8 API routers, all under /api/v1
│   ├── auth.py
│   ├── uploads.py
│   ├── conversions.py
│   ├── slides.py
│   ├── export.py
│   ├── users.py
│   ├── admin.py
│   └── templates.py
└── services/
    ├── claude.py            # Gemini 2.5 Flash + Claude Sonnet + stub slides for dev
    ├── gcs.py               # GCS + local dev fallback
    ├── parser.py            # PDF, DOCX, PPTX, Markdown parsing
    ├── pptx_builder.py      # python-pptx PPTX generation
    ├── themes.py            # 18 Theme definitions and styling
    └── audit.py             # log_event() helper
```

## API Endpoints (all under /api/v1)

### Auth
- `POST /auth/register` — Register; returns TokenResponse
- `POST /auth/login` — Login; returns access token + sets httpOnly refresh_token cookie
- `POST /auth/refresh` — Refresh access token (reads httpOnly cookie, rotates token)
- `PATCH /auth/password` — Change password (requires auth)
- `POST /auth/logout` — Revoke refresh token

### Uploads
- `POST /uploads/presign` — Get GCS presigned PUT URL (or local dev URL)
- `PUT /uploads/{id}/local` — Local dev fallback: accept file bytes directly
- `POST /uploads/{id}/confirm` — Mark upload complete, trigger parsing
- `GET /uploads/{id}/preview` — Get parsed text preview
- `GET /uploads` — List user's uploads (paginated)

### Conversions
- `POST /conversions` — Create conversion (upload_id OR prompt_text)
- `GET /conversions` — List user's conversions (paginated)
- `GET /conversions/{id}` — Conversion detail + slides
- `GET /conversions/{id}/slides` — List slides
- `POST /conversions/{id}/slides` — Insert slide at position
- `POST /conversions/{id}/slides/reorder` — Reorder slides
- `POST /conversions/{id}/cancel` — Cancel pending conversion
- `DELETE /conversions/{id}` — Delete (owner or admin)
- `GET /conversions/{id}/stream` — SSE stream for generation progress

### Slides
- `PATCH /slides/{id}` — Update title/bullets/speaker_notes/layout/color_scheme/shape_style
- `DELETE /slides/{id}` — Soft delete (sets is_deleted=true)
- `POST /slides/{id}/ai-enhance` — Claude-powered content improvement
- `POST /slides/{id}/restore` — Restore soft-deleted slide

### Export
- `POST /conversions/{id}/export` — Build PPTX, upload to GCS
- `GET /conversions/{id}/download` — Local dev: stream PPTX bytes directly

### Users
- `GET /users/me` — Current user profile

### Admin (require_admin)
- `GET /admin/metrics` — Dashboard: user count, conversions, costs, success rate
- `GET /admin/users` — All users (paginated, searchable)
- `GET /admin/users/{id}` — User detail
- `PATCH /admin/users/{id}` — Suspend/activate user or change role
- `GET /admin/conversions` — All conversions (paginated)
- `GET /admin/audit-log` — Audit log (paginated)

### Templates
- `POST /templates` — Admin: upload template PPTX
- `GET /templates` — List active templates
- `GET /templates/{id}` — Template detail
- `POST /templates/{id}/copy` — Copy template slides into a new conversion
- `DELETE /templates/{id}` — Admin: deactivate template

## Data Models

### Slide (important fields)
```python
class Slide(Base):
    id: UUID
    conversion_id: UUID
    position: int
    layout: str          # hero | bullets | two_column | image_text | closing
    title: str
    bullets: list        # JSONB; two_column uses "## Header" prefix convention
    speaker_notes: str
    color_scheme: str    # e.g. "default", "dark", "vibrant"
    shape_style: str     # e.g. "square", "rounded", "circle"
    is_deleted: bool     # soft delete — always filter WHERE is_deleted = false
    deleted_at: datetime
```

### Conversion status flow
`pending` → `generating` → `done` | `failed` | `cancelled`

## Conversion Pipeline
1. Client `POST /conversions` with `upload_id` OR `prompt_text` (+ optional `presentation_flags`)
2. If upload: parse document text via `services/parser.py`
3. Build system prompt via `services/claude.build_system_prompt()` (injects flag instructions)
4. Call AI (Gemini 2.5 Flash preferred, Claude Sonnet fallback, stub if no key) → `{"slides": [...]}` JSON
5. Post-process: `validate_slides()` enforces per-layout bullet rules
6. Post-process: roadmap flag enforcement — guarantees a `timeline` slide exists
7. Each slide saved to `slides` table with `color_scheme` + `shape_style`
8. Frontend streams progress via `GET /conversions/{id}/stream` (SSE)
9. Export: `POST /conversions/{id}/export` → `pptx_builder` → GCS or local

### Prompt-only mode (no file upload)
```python
# conversions.py create_conversion()
if body.prompt_text and not body.upload_id:
    display_name = (body.prompt_text[:57] + "…") if len(body.prompt_text) > 57 else body.prompt_text
    doc_text = body.prompt_text
    # no upload row; upload_id=None on conversion
else:
    # file upload flow — sets upload = await db.get(Upload, body.upload_id)
```

### Stub slides for dev (no API key)
`services/claude._stub_slides()` returns a 10-slide pitch deck when
neither `GEMINI_API_KEY` nor a real `ANTHROPIC_API_KEY` is set. Every
stub slide includes `color_scheme` and `shape_style` fields. Two-column
slides use `## Header` prefix on bullets to denote column splits.

### Presentation flags (`presentation_flags`)
Optional list of strings sent with `POST /conversions`. Each flag injects
extra instructions into the system prompt AND triggers server-side enforcement:

| Flag | Prompt instruction | Server enforcement |
|------|-------------------|--------------------|
| `minimal` | Max 3 bullets, prefer hero/bullets layouts | None (soft prompt only) |
| `roadmap` | Include exactly one `timeline` slide | Post-process: if no timeline slide, convert best matching slide or insert one at position 2 |
| `data_focus` | Prefer `big_stat`/`data_table` layouts | None (soft prompt only) |

Roadmap enforcement logic (in `conversions.py _generate_slides_task()`):
1. Check if any slide has `layout == "timeline"` after `validate_slides()`
2. If not, scan slide titles for roadmap keywords; convert matching slide to timeline with `"Phase N: ..."` bullets
3. If no keyword match found, insert a default 3-phase timeline slide at position 2

### AI provider selection (priority order)
1. **Gemini 2.5 Flash** — used when `GEMINI_API_KEY` is set (primary provider)
   - `thinking_budget=0` disables thinking tokens for reliable JSON output
   - Text extraction falls back through `.text` → `.candidates[0].content.parts[0].text`
   - JSON scanned with `text.find("{")` + `json.JSONDecoder().raw_decode()` to handle surrounding text
2. **Claude Sonnet 4.5** — used when a valid `ANTHROPIC_API_KEY` is set (`sk-ant-...` prefix)
3. **Stub slides** — used in dev when neither key is present

### Themes (18 total in `services/themes.py`)
Valid theme IDs — **do not use any other ID as default or fallback**:
```
Professional: clean_slate, navy_gold, dark_tech, charcoal_amber, steel_blue, forest_pro
Creative:     vivid_purple, sunset_orange, ocean_teal, neon_blue, ruby_red, cosmic_indigo
Minimal:      pure_white, warm_ivory, soft_grey, light_pearl, sage_mist, warm_slate
```
Default/fallback theme is always `"clean_slate"`. `"executive_gold"` does NOT exist.

## FastAPI conventions
- All route handlers: `async def`
- All dependencies injected via `Depends()`
- Return typed Pydantic v2 response schemas always
- Raise `HTTPException` with `detail` as dict, never plain string
- Router prefix pattern: `/api/v1/{resource}`
- Apply `Depends(get_current_user)` or `Depends(require_admin)` on every
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

## Database Syntax — asyncpg caveat
**Never use `::jsonb` PostgreSQL cast syntax in parameterized queries.**
The `:` character conflicts with asyncpg's named-parameter parsing and
silently breaks queries (caused a login regression when audit log changes
introduced `::jsonb`).

Use `CAST(... AS jsonb)` instead:
```python
# BAD
sa.text("SELECT * FROM t WHERE data::jsonb @> :val")

# GOOD
sa.text("SELECT * FROM t WHERE CAST(data AS jsonb) @> :val")
```

## AI API patterns (use tenacity for retry)

### Gemini 2.5 Flash (primary)
```python
from google import genai
from google.genai import types

client = genai.Client(api_key=settings.GEMINI_API_KEY)
response = await client.aio.models.generate_content(
    model="gemini-2.5-flash",
    contents=user_message,
    config=types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=8192,
        thinking_config=types.ThinkingConfig(thinking_budget=0),  # required for JSON reliability
    ),
)
# Safe text extraction — .text can throw on thinking models
text = None
try:
    text = response.text
except Exception:
    pass
if not text:
    text = response.candidates[0].content.parts[0].text
text = strip_fences(text.strip())
start = text.find("{")
result, _ = json.JSONDecoder().raw_decode(text, start)  # handles surrounding text
```

### Claude Sonnet 4.5 (fallback)
```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
response = await client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=8192,
    system=system,
    messages=[{"role": "user", "content": user_message}]
)
text = strip_fences(response.content[0].text.strip())
result = json.loads(text)
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

### Local dev file fallback
When `ENVIRONMENT=development` and GCS credentials are absent,
`services/gcs.py` falls back to local filesystem (`/tmp/pitchmind/`).
The `PUT /uploads/{id}/local` endpoint accepts raw file bytes so
the frontend can upload without a real GCS bucket.

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

## Environment Variables (complete list)
```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/pitchmind
REDIS_URL=redis://localhost:6379

# AI provider — set one (Gemini takes priority over Anthropic)
GEMINI_API_KEY=AIza...                 # preferred; enables Gemini 2.5 Flash
ANTHROPIC_API_KEY=sk-ant-...          # fallback; omit both to use stub slides in dev

JWT_SECRET=your_secret_here
JWT_ACCESS_EXPIRE_MINUTES=30
JWT_REFRESH_EXPIRE_DAYS=30

# Google Cloud Storage
GCS_PROJECT_ID=your-project
GCS_BUCKET=pitchmind-files
GCS_CREDENTIALS_JSON=/path/to/key.json   # omit to use local fallback in dev

FRONTEND_URL=http://localhost:5173
ENVIRONMENT=development                  # or production
```

## Testing conventions
- All test files in `tests/`
- `pytest.ini`: `asyncio_mode = "auto"`
- Mock Claude API with pytest-mock — NEVER call real API in tests
- Use `httpx.AsyncClient(app=app, base_url="http://test")` for routes
- Fixtures in `conftest.py`: `test_db`, `test_client`, `test_user`, `test_admin`
- Unit tests: pure functions, no DB, no external services
- Integration tests: test full HTTP request/response cycle with test DB
- Always assert both success and failure cases

## Alembic rules
- Single migration file: `001_initial_schema.py` — all tables
- Never edit a migration after `alembic upgrade head` has been run
- Test: `alembic upgrade head` then `alembic downgrade -1` before commit
- `gen_random_uuid()` is built-in since PG 14 — no pgcrypto extension needed

## Startup (local, no Docker)
PostgreSQL 17 lives at `/home/wac/pgdata` (Miniconda3 install).
Run `/home/wac/start-pitchmind.sh` after every system restart — it starts
Postgres, FastAPI (port 8000), and the React dev server (port 5173).

```bash
bash ~/start-pitchmind.sh
# Logs: /tmp/pitchmind-backend.log  /tmp/pitchmind-frontend.log
```

## GCS bucket setup (do once in GCP Console)
1. Create bucket: `pitchmind-files` (region: us-central1)
2. Create service account with role: Storage Object Admin
3. Download JSON key → set `GCS_CREDENTIALS_JSON` path in env
4. Set CORS:
   ```
   gsutil cors set cors.json gs://pitchmind-files
   ```
   `cors.json`:
   ```json
   [{"origin":["https://your-app.vercel.app"],
     "method":["PUT","GET"],"maxAgeSeconds":3600}]
   ```

## Docker development workflow
NOTE: `docker-compose.yml` lives in `pitchmind-backend/` only.
The frontend runs locally with `npm run dev` — no Docker needed for it.

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
Railway auto-detects `Dockerfile` in repo root.
Set all env vars in Railway dashboard → Variables.
Migration must run manually once after first deploy:
```bash
railway run alembic upgrade head
```
