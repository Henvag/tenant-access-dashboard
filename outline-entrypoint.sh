#!/bin/sh
set -eu

# Prefer a dedicated Outline DB URL from the dashboard bootstrap endpoint
# (needed when DATABASE_URL was overwritten and fromDatabase can't be re-linked via API).
if [ -n "${OUTLINE_DB_BOOTSTRAP_URL:-}" ] && [ -n "${OUTLINE_DB_BOOTSTRAP_TOKEN:-}" ]; then
  BOOTSTRAPED=$(node -e '
const https = require("https");
const url = process.env.OUTLINE_DB_BOOTSTRAP_URL;
const token = process.env.OUTLINE_DB_BOOTSTRAP_TOKEN;
https.get(url, { headers: { Authorization: "Bearer " + token } }, (res) => {
  let data = "";
  res.on("data", (c) => (data += c));
  res.on("end", () => {
    if (res.statusCode !== 200 || !data) process.exit(1);
    process.stdout.write(data.trim());
  });
}).on("error", () => process.exit(1));
' || true)
  if [ -n "${BOOTSTRAPED:-}" ]; then
    DATABASE_URL="$BOOTSTRAPED"
    export DATABASE_URL
  fi
fi

if [ -n "${DATABASE_URL:-}" ]; then
  # Point at the dedicated outline DB created by migration 010.
  DATABASE_URL=$(printf '%s' "$DATABASE_URL" | sed -E 's#/[^/?]+(\?|$)#/outline\1#')
  export DATABASE_URL
fi

# Outline 1.x image CMD is `node build/server/index.js` (no yarn start).
cd /opt/outline
exec node build/server/index.js
