#!/bin/sh
# Fetch what the film needs but the repo does not carry: GSAP and the Schibsted Grotesk font.
set -eu
cd "$(dirname "$0")/.."
mkdir -p assets/vendor assets/fonts

tmp=$(mktemp -d)
(cd "$tmp" && npm pack gsap@3.15.0 --silent >/dev/null && tar xzf gsap-3.15.0.tgz)
cp "$tmp/package/dist/gsap.min.js" assets/vendor/gsap.min.js
rm -rf "$tmp"

# Google Fonts serves one variable file for the latin subset.
ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
url=$(curl -fsS -A "$ua" "https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400..700&display=swap" \
  | awk '/\/\* latin \*\//{f=1} f && /src:/{print; exit}' | sed -E 's/.*url\(([^)]+)\).*/\1/')
curl -fsS -o assets/fonts/SchibstedGrotesk-latin-var.woff2 "$url"
echo "assets ready"
