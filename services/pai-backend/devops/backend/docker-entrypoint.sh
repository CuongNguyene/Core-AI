#!/usr/bin/env sh
set -eu

if [ "${1:-api}" = "api" ]; then
  uv run alembic upgrade head
  exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
fi

exec "$@"
