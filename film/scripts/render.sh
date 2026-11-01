#!/bin/sh
# Render the film in one language: sh scripts/render.sh en|no
# The scenes read their language from the hosts' data-variable-values in index.html, and a
# render's --variables only reaches the root, so the Norwegian render runs from a copy of
# the project with those values switched.
set -eu
lang="${1:-en}"
case "$lang" in en | no) ;; *) echo "usage: sh scripts/render.sh en|no" >&2; exit 1 ;; esac
cd "$(dirname "$0")/.."
mkdir -p renders
out="$(pwd)/renders/tenant-access-film-$lang.mp4"

src="."
if [ "$lang" != en ]; then
  src=$(mktemp -d)
  cp -R index.html hyperframes.json compositions assets "$src"/
  sed "s/{\"lang\":\"en\"}/{\"lang\":\"$lang\"}/g" index.html > "$src/index.html"
fi
npx --yes hyperframes@0.8.225 render "$src" -o "$out"
[ "$src" = "." ] || rm -rf "$src"
echo "$out"
