from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import os

from app.core.config import get_settings
from app.routers import auth, uploads, conversions, slides, export, users, admin, templates, ai

settings = get_settings()

app = FastAPI(
    title="PitchMind API",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
)

_origins = (
    [settings.FRONTEND_URL]
    if settings.ENVIRONMENT != "development"
    else [settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:5174"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"http://localhost:\d+" if settings.ENVIRONMENT == "development" else None,
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
app.include_router(ai.router, prefix=PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.ENVIRONMENT}


# Find frontend dist directory
frontend_dist = None
possible_paths = [
    Path(__file__).parent.parent / "frontend_dist",  # ./frontend_dist (included in deployment)
    Path(__file__).parent.parent.parent / "pitchmind-react" / "dist",  # ../pitchmind-react/dist (for local dev)
    Path("/workspace/pitchmind-react/dist"),
    Path("/app/pitchmind-react/dist"),
    Path("./pitchmind-react/dist"),
    Path("./frontend_dist"),
]

for path in possible_paths:
    if path.is_dir():
        frontend_dist = path
        break

# Serve frontend assets
if frontend_dist and (frontend_dist / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

# Catch-all route for SPA - serve index.html for non-API routes
if frontend_dist:
    @app.api_route("/{path:path}", methods=["GET"])
    async def serve_spa(path: str):
        # Don't serve SPA for API routes, docs, or health
        if path.startswith(("api/", "docs", "openapi.json", "health")):
            return {"error": "not found"}
        
        # Skip static assets that should be served by the mount
        if path.startswith("assets/"):
            return {"error": "not found"}
        
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "PitchMind API", "api": "/api/v1", "health": "/health"}
else:
    @app.get("/")
    async def root():
        return {"message": "PitchMind API", "api": "/api/v1", "health": "/health"}



