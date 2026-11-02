#!/bin/sh
set -e
cd /app/backend

# Migrations run before the server starts. A run that hangs keeps the port closed
# until Render fails the deploy, so cap it and try once more: if the first run
# committed and then got stuck, the second one finds nothing to do.
if ! timeout 180 alembic upgrade head; then
  echo "alembic upgrade did not finish, trying once more" >&2
  timeout 180 alembic upgrade head
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
