#!/bin/bash
set -e

# Convert postgres:// or postgresql:// to postgresql+asyncpg:// for SQLAlchemy async
if [[ "$DATABASE_URL" == postgres://* ]]; then
  export DATABASE_URL="${DATABASE_URL/postgres:\/\//postgresql+asyncpg:\/\/}"
elif [[ "$DATABASE_URL" == postgresql://* ]]; then
  export DATABASE_URL="${DATABASE_URL/postgresql:\/\//postgresql+asyncpg:\/\/}"
fi

echo "DATABASE_URL prefix: ${DATABASE_URL%%:*}"
echo "REDIS_URL prefix: ${REDIS_URL%%:*}"
echo "ENVIRONMENT: $ENVIRONMENT"

echo "Running database migrations..."
alembic upgrade head || echo "WARNING: Migrations failed, continuing..."

echo "Starting server..."
exec gunicorn app.main:app \
  -w 1 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:${PORT:-8000} \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
