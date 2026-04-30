from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import auth, uploads, conversions, slides, export, users, admin, templates

settings = get_settings()

app = FastAPI(
    title="PitchMind API",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/v1"

app.include_router(auth.router, prefix=PREFIX)
app.include_router(uploads.router, prefix=PREFIX)
app.include_router(conversions.router, prefix=PREFIX)
app.include_router(slides.router, prefix=PREFIX)
app.include_router(export.router, prefix=PREFIX)
app.include_router(users.router, prefix=PREFIX)
app.include_router(admin.router, prefix=PREFIX)
app.include_router(templates.router, prefix=PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.ENVIRONMENT}
