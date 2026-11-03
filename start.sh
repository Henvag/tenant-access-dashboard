#!/bin/sh
set -e
cd /app/backend

# A version only migrates the database once it has shown it can start, and a
# version that finds the database ahead of it still starts. On 2 and 3 November
# 2026 three deploys migrated the database and then never opened their port, and
# the previous version couldn't start on the migrated database. See
# app/preflight.py.
status=0
timeout 180 python -m app.preflight || status=$?

case "$status" in
  4) ;;  # nothing to migrate
  3) echo "start.sh: starting without migrating" >&2 ;;
  0)
    # A run that hangs keeps the port closed until Render fails the deploy, so
    # cap it and try once more: if the first run committed and then got stuck,
    # the second one finds nothing to do.
    echo "start.sh: running migrations" >&2
    if ! timeout 180 alembic upgrade head; then
      echo "start.sh: alembic upgrade did not finish, trying once more" >&2
      timeout 180 alembic upgrade head
    fi
    ;;
  *)
    echo "start.sh: start check failed (exit $status), database left as it is" >&2
    exit "$status"
    ;;
esac

echo "start.sh: starting the server" >&2
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
