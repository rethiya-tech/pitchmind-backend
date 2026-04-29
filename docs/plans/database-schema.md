# Database Schema — PitchMind Phase 1

Single Alembic migration: 001_initial_schema.py
All tables use UUID PKs via gen_random_uuid().

```sql
-- USERS
CREATE TABLE users (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email          VARCHAR(255) UNIQUE NOT NULL,
  password_hash  VARCHAR(255) NOT NULL,
  name           VARCHAR(255),
  role           VARCHAR(20) NOT NULL DEFAULT 'user'
                 CHECK (role IN ('user', 'admin')),
  is_active      BOOLEAN NOT NULL DEFAULT true,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_login     TIMESTAMPTZ,
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_email ON users(email);

-- REFRESH TOKENS
CREATE TABLE refresh_tokens (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash  VARCHAR(255) NOT NULL,
  expires_at  TIMESTAMPTZ NOT NULL,
  revoked     BOOLEAN NOT NULL DEFAULT false,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_rt_user_revoked ON refresh_tokens(user_id, revoked);

-- UPLOADS
CREATE TABLE uploads (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID REFERENCES users(id) ON DELETE SET NULL,
  gcs_key           VARCHAR(500) NOT NULL,
  original_filename VARCHAR(500) NOT NULL,
  file_size_bytes   INTEGER NOT NULL,
  mime_type         VARCHAR(100) NOT NULL,
  parse_status      VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (parse_status IN ('pending','done','failed')),
  parsed_doc        JSONB,
  parsed_preview    TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- CONVERSIONS
CREATE TABLE conversions (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID REFERENCES users(id) ON DELETE SET NULL,
  upload_id        UUID REFERENCES uploads(id) ON DELETE SET NULL,
  original_filename VARCHAR(500),
  status           VARCHAR(20) NOT NULL DEFAULT 'pending'
                   CHECK (status IN
                   ('pending','generating','done','failed','cancelled')),
  style            VARCHAR(100),
  slide_count      INTEGER,
  theme            VARCHAR(100),
  audience_level   VARCHAR(50),
  speaker_notes    BOOLEAN NOT NULL DEFAULT true,
  tokens_used      INTEGER NOT NULL DEFAULT 0,
  retry_count      INTEGER NOT NULL DEFAULT 0,
  error_message    TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at     TIMESTAMPTZ
);
CREATE INDEX idx_conv_user_created ON conversions(user_id, created_at DESC);
CREATE INDEX idx_conv_status ON conversions(status);

-- SLIDES
CREATE TABLE slides (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversion_id  UUID NOT NULL REFERENCES conversions(id) ON DELETE CASCADE,
  position       INTEGER NOT NULL,
  layout         VARCHAR(50) NOT NULL DEFAULT 'bullets',
  title          VARCHAR(500),
  bullets        JSONB NOT NULL DEFAULT '[]',
  speaker_notes  TEXT,
  is_deleted     BOOLEAN NOT NULL DEFAULT false,
  deleted_at     TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_slides_conv_pos
  ON slides(conversion_id, position)
  WHERE is_deleted = false;

-- AUDIT LOG
CREATE TABLE audit_log (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id    UUID REFERENCES users(id) ON DELETE SET NULL,
  action      VARCHAR(100) NOT NULL,
  target_type VARCHAR(50),
  target_id   UUID,
  metadata    JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);
```
