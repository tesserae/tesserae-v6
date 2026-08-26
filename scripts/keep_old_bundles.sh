#!/usr/bin/env bash
# Keep the last few frontend bundles on disk after a deploy.
#
# WHY. Apache falls back to index.html for any path it cannot find, so once a
# build is deleted, a browser holding a cached page asks for it and receives
# 200 OK with Content-Type text/html -- the PAGE, pretending to be JavaScript.
# The browser fails to parse it and NOTHING runs: no app, no error handler, no
# message. It looks like the site is broken rather than out of date.
#
# Keeping the previous bundles turns that hard failure into a soft one: the
# stale page loads its old JavaScript and works, one version behind, and
# UpdateBanner tells the reader to reload.
#
# The files are left UNTRACKED, so `git pull` does not remove them again.
#
# The real fix is a Cache-Control header on index.html, which needs a change to
# the Apache vhost and therefore root. This is the half that does not.
#
# Usage, on the production host, BEFORE git pull:
#     scripts/keep_old_bundles.sh save
# and AFTER:
#     scripts/keep_old_bundles.sh restore
set -euo pipefail

DIST="${DIST:-/var/www/tesseraev6_flask/dist}"
ATTIC="${ATTIC:-/var/www/tesseraev6_flask/.bundle-attic}"
KEEP="${KEEP:-8}"

mkdir -p "$ATTIC"

case "${1:-}" in
  save)
    cp -n "$DIST"/assets/index-*.js "$DIST"/assets/index-*.css "$ATTIC"/ 2>/dev/null || true
    echo "saved $(ls -1 "$ATTIC" | wc -l) bundle files"
    ;;
  restore)
    n=0
    for f in "$ATTIC"/*; do
      [ -e "$f" ] || continue
      b="$(basename "$f")"
      if [ ! -e "$DIST/assets/$b" ]; then cp "$f" "$DIST/assets/$b"; n=$((n+1)); fi
    done
    # Prune the attic to the newest KEEP files so it cannot grow without bound.
    ls -1t "$ATTIC" | tail -n +$((KEEP + 1)) | while read -r old; do rm -f "$ATTIC/$old"; done
    echo "restored $n older bundle(s); attic holds $(ls -1 "$ATTIC" | wc -l)"
    ;;
  *)
    echo "usage: $0 save|restore" >&2; exit 2 ;;
esac
