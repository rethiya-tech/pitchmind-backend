# Build Progress — PitchMind

## Repository
Backend:  github.com/your-org/pitchmind-backend  → Railway
Frontend: github.com/your-org/pitchmind-frontend → Vercel

## Current status
Day: Initialization complete — ready to start Day 1 backend
Last updated: 2026-04-28

## Day 1 — Backend (target: all backend working)
### Setup
- [x] Project scaffold created
- [x] requirements.txt written
- [ ] config.py — Settings from env vars
- [ ] database.py — async SQLAlchemy engine + session
- [ ] security.py — JWT encode/decode, bcrypt
- [ ] Alembic migration — all 6 tables
- [ ] alembic upgrade head confirmed working
### Auth
- [ ] POST /auth/register
- [ ] POST /auth/login
- [ ] POST /auth/refresh
- [ ] POST /auth/logout
- [ ] get_current_user dependency
- [ ] require_admin dependency
### Upload
- [ ] POST /uploads/presign (GCS signed URL)
- [ ] POST /uploads/confirm (verify GCS, save, trigger parse)
- [ ] GET /uploads/:id/preview
- [ ] PDF parser (pdfplumber)
- [ ] DOCX parser (python-docx)
- [ ] TXT/MD parser (markdown-it-py)
- [ ] ParsedDocument dataclass
### AI Generation
- [ ] POST /conversions
- [ ] GET /conversions/:id/stream (SSE)
- [ ] Claude system prompt + call + retry
- [ ] JSON slide validation
- [ ] POST /conversions/:id/cancel
- [ ] Token tracking (tokens_used column)
### Export
- [ ] 6 Theme dataclasses
- [ ] python-pptx builder
- [ ] GET /conversions/:id/export/pptx → GCS + signed URL
### User + Admin
- [ ] GET /users/me
- [ ] GET /conversions (own list)
- [ ] GET /conversions/:id (with slides)
- [ ] GET /admin/metrics
- [ ] GET /admin/users
- [ ] PATCH /admin/users/:id
- [ ] GET /admin/audit-log
- [ ] Audit log writes on admin actions
- [ ] GET /health

## Day 2 — Frontend (target: all screens working)
### Setup
- [ ] Vite + React + TypeScript scaffold
- [ ] Tailwind with pm-* tokens
- [ ] Plus Jakarta Sans font imported
- [ ] React Router 6 all routes
- [ ] Zustand: authStore, editorStore, uiStore
- [ ] Axios client + interceptors
- [ ] ProtectedRoute + AdminRoute
### Screens
- [ ] LoginPage
- [ ] RegisterPage
- [ ] DashboardPage
- [ ] UploadPage (dropzone + GCS upload + preview)
- [ ] SettingsPage (all settings)
- [ ] GeneratingPage (SSE pills + progress)
- [ ] EditorPage (full editor)
- [ ] ExportPage
- [ ] AdminDashboardPage
- [ ] AdminUsersPage
- [ ] AdminAuditLogPage
### Editor
- [ ] SlideCanvas (16:9 themed render)
- [ ] ThumbnailStrip (dnd-kit)
- [ ] InlineText (contenteditable title)
- [ ] BulletList (inline bullet editing)
- [ ] Auto-save 500ms debounce
- [ ] Autosaved indicator in toolbar
- [ ] Drag-and-drop reorder
- [ ] Insert blank slide
- [ ] Delete + 5s undo toast
- [ ] Layout switcher
- [ ] Speaker notes
- [ ] AI Rewrite drawer
- [ ] Zoom controls

## Day 3 — Polish + Deploy
- [ ] All buttons wired to real API
- [ ] Loading states on all buttons
- [ ] Error states (upload fail, generate fail, export fail)
- [ ] Toast notifications
- [ ] Full flow tested end-to-end
- [ ] Admin flow tested
- [ ] Dockerfile written and tested locally
- [ ] Backend deployed to Railway
- [ ] Env vars set in Railway
- [ ] alembic upgrade head on prod DB
- [ ] Frontend deployed to Vercel
- [ ] Env vars set in Vercel
- [ ] /health returns 200 on production URL
- [ ] Full flow tested on production URL

## Blockers
None

## Notes
(update as you go)
