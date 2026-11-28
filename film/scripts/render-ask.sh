#!/bin/sh
# Render the Ask clip in one language: sh scripts/render-ask.sh en|no
# The clip is ask.html; it renders from a copy of the project where it is index.html,
# with the language set on its root.
set -eu
lang="${1:-en}"
case "$lang" in en | no) ;; *) echo "usage: sh scripts/render-ask.sh en|no" >&2; exit 1 ;; esac
cd "$(dirname "$0")/.."
mkdir -p renders
out="$(pwd)/renders/tenant-access-ask-$lang.mp4"
src=$(mktemp -d)
cp -R hyperframes.json assets "$src"/
sed "s/data-lang=\"en\"/data-lang=\"$lang\"/" ask.html > "$src/index.html"
npx --yes hyperframes@0.8.225 render "$src" -o "$out"
rm -rf "$src"
echo "$out"
