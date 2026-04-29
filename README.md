# PitchMind Backend

FastAPI backend for PitchMind — AI-powered document-to-presentation web app.

## Quick Start (Docker)

```bash
cp .env.example .env
# Fill in your values in .env
docker compose up -d db redis
docker compose run --rm migrate
docker compose up backend
```

Visit http://localhost:8000/api/v1/health

## Quick Start (without Docker)

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in DATABASE_URL and other vars
alembic upgrade head
uvicorn app.main:app --reload
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `TEST_DATABASE_URL` | Test database URL |
| `REDIS_URL` | Redis URL for rate limiting |
| `ANTHROPIC_API_KEY` | Anthropic API key for claude-sonnet-4 |
| `JWT_SECRET` | 256-bit random secret for JWT signing |
| `GCS_PROJECT_ID` | Google Cloud project ID |
| `GCS_BUCKET` | GCS bucket name (e.g. `pitchmind-files`) |
| `GCS_CREDENTIALS_JSON` | Path to GCS service account JSON key |
| `FRONTEND_URL` | Frontend origin for CORS (e.g. `https://app.vercel.app`) |
| `ENVIRONMENT` | `development` or `production` |

## GCS Bucket Setup

1. Create bucket `pitchmind-files` in GCP Console (region: us-central1)
2. Create service account with role: Storage Object Admin
3. Download JSON key → set `GCS_CREDENTIALS_JSON` in .env
4. Set CORS on bucket:
   ```bash
   gsutil cors set cors.json gs://pitchmind-files
   ```
   Where `cors.json`:
   ```json
   [{"origin": ["https://your-app.vercel.app"], "method": ["PUT", "GET"],
     "responseHeader": ["Content-Type"], "maxAgeSeconds": 3600}]
   ```

## Running Tests

```bash
pytest tests/ -v --asyncio-mode=auto
```

## Deployment

Deploy to Railway. Railway auto-detects the Dockerfile.

1. Push to GitHub
2. Connect repo to Railway
3. Set all env vars in Railway → Variables
4. After first deploy, run migration:
   ```bash
   railway run alembic upgrade head
   ```

## Related

- Frontend: [pitchmind-frontend](https://github.com/your-org/pitchmind-frontend)
