# API Contracts — PitchMind Phase 1

Base: /api/v1  |  Auth: Bearer JWT  |  Format: JSON

## Auth

POST /auth/register
  In:  { email, password, name }
  Out: { message: "Registration successful" }
  Err: 409 email exists

POST /auth/login
  In:  { email, password }
  Out: { access_token, token_type: "bearer",
         user: { id, email, name, role } }
  Sets: httpOnly cookie refresh_token

POST /auth/refresh
  In:  httpOnly cookie
  Out: { access_token, user }

POST /auth/logout
  In:  httpOnly cookie
  Out: { message: "Logged out" }

## Upload

POST /uploads/presign
  In:  { filename, content_type, size_bytes }
  Out: { upload_url, gcs_key }

POST /uploads/confirm
  In:  { gcs_key, filename, file_size_bytes, mime_type }
  Out: { upload_id, parse_status }

GET /uploads/:id/preview
  Out: { preview_text, word_count }

## Conversions

POST /conversions
  In:  { upload_id, style, slide_count, theme,
         audience_level, speaker_notes }
  Out: { id, estimated_slides, estimated_seconds }

GET /conversions
  Out: [{ id, original_filename, status, slide_count,
          created_at, completed_at }]

GET /conversions/:id
  Out: { id, status, style, theme, slide_count,
         slides: [{ id, position, layout, title,
                    bullets, speaker_notes }] }

GET /conversions/:id/stream  (SSE, ?token=JWT)
  Events:
    slide_start  { index, total }
    slide_done   { slide: { id, position, layout, title,
                             bullets, speaker_notes } }
    progress     { completed, total }
    error        { message, last_index }
    done         { conversion_id, total_slides }
  Comment: ": keepalive" every 10s

POST /conversions/:id/cancel
  Out: { message: "Cancelled", slides_completed: N }

## Slides

PATCH /conversions/:id/slides/:slideId
  In:  { title?, bullets?, speaker_notes?, layout? }
  Out: { id, position, layout, title, bullets,
         speaker_notes, updated_at }

PATCH /conversions/:id/slides/reorder
  In:  { slide_ids: [uuid, ...] }
  Out: { success: true }

POST /conversions/:id/slides
  In:  { position }
  Out: { id, position, layout: "bullets", title: "",
         bullets: [], speaker_notes: "" }

DELETE /conversions/:id/slides/:slideId
  Out: { message: "Soft deleted", id }

PATCH /conversions/:id/slides/:slideId/restore
  Out: { id, position, layout, title, bullets }

## Export

GET /conversions/:id/export/pptx
  Out: { download_url, expires_at }

## User

GET /users/me
  Out: { id, email, name, role, created_at }

## Admin (require_admin)

GET /admin/metrics
  Out: { total_users, conversions_today, failed_today, ai_cost_today_usd }

GET /admin/users?page=1&search=
  Out: { users: [{ id, email, name, role, is_active,
                   created_at, conversion_count }], total, page }

PATCH /admin/users/:id
  In:  { action: "suspend"|"reinstate"|"promote"|"demote" }
  Out: { id, email, role, is_active }

GET /admin/audit-log?page=1
  Out: { logs: [{ id, actor_email, action, target_type,
                  target_id, metadata, created_at }], total, page }

GET /health
  Out: { status: "ok", db: "ok", env: "production" }
