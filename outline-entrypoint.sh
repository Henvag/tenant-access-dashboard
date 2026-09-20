#!/bin/sh
set -eu

if [ -n "${DATABASE_URL:-}" ]; then
  # Point at the dedicated outline DB created by migration 010.
  DATABASE_URL=$(printf '%s' "$DATABASE_URL" | sed -E 's#/[^/?]+(\?|$)#/outline\1#')
  export DATABASE_URL
fi

exec docker-entrypoint.sh yarn start
