#!/usr/bin/env bash
# Build the redistributable Tesserae data bundle from the production data, with
# every private part left out. Nothing is published by this script. It writes
# a tar.zst, MANIFEST.tsv, LICENSES.md and a checksum into the output folder.
#
#   scripts/ops/build_public_bundle.sh --core            texts, lemma caches, indexes, translations, documents
#   scripts/ops/build_public_bundle.sh --full            core plus passage index, vectors, reuse tables, names, map
#   scripts/ops/build_public_bundle.sh --core --measure  add up sizes only, build nothing
#
# Options: --out DIR (default ~/tesserae-backups/public-bundle)
#          --prod DIR (default /var/www/tesseraev6_flask, read only)
#
# What goes in and what stays out is decided by scripts/ops/public_bundle_exclusions.json
# and scripts/ops/public_bundle_lib.py. The full bundle needs the passage index
# filtered to the bundled languages first (scripts/ops/filter_passage_index.py).
# Heavy steps run under ~/bin/tess-job and wait, polling every two minutes,
# if the job budget is taken.
set -uo pipefail

SELF=$(readlink -f "$0")
HERE=$(dirname "$SELF")
REPO=$(dirname "$(dirname "$HERE")")
PROD=/var/www/tesseraev6_flask
OUT=$HOME/tesserae-backups/public-bundle
MODE=""; MEASURE=0
PY=${PYTHON:-}
if [[ -z "$PY" ]]; then
  for c in "$HOME/tesserae-v6-dev/venv/bin/python3" python3; do command -v "$c" >/dev/null 2>&1 && { PY=$c; break; }; done
fi
MIN_FREE_GB=120

# internal entry point used inside tess-job: the archive step
if [[ "${1:-}" == "--_tar" ]]; then
  WORK=$2; PRODIR=$3; DEST=$4
  # pax format keeps modification times to the nanosecond. The corpus frequency cache is keyed on them, and a
  # plain tar rounds them to the second, which would make every unpacked cache look stale.
  tar --format=posix --pax-option=delete=atime,delete=ctime --null -cf - -C "$PRODIR" -T "$WORK/files.prod.null" -C "$WORK/stage" -T "$WORK/files.stage.null" \
    | zstd -T4 -3 -q -o "$DEST.partial" -f
  rcs=("${PIPESTATUS[@]}")
  # tar exit 1 means a file changed while it was read: accept, the manifest hash check below catches content drift
  [[ ${rcs[0]} -le 1 && ${rcs[1]} -eq 0 ]] || { echo "archive step failed: ${rcs[*]}" >&2; exit 1; }
  mv "$DEST.partial" "$DEST"
  exit 0
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --core) MODE=core ;;
    --full) MODE=full ;;
    --measure) MEASURE=1 ;;
    --out) OUT=$2; shift ;;
    --prod) PROD=$2; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
  shift
done
[[ -n "$MODE" ]] || { echo "usage: $0 --core|--full [--measure] [--out DIR] [--prod DIR]" >&2; exit 2; }

free_gb=$(df --output=avail -BG / | tail -1 | tr -dc 0-9)
if (( free_gb < MIN_FREE_GB )); then
  echo "STOP: ${free_gb} GB free on /, below the ${MIN_FREE_GB} GB this script needs" >&2
  exit 1
fi
[[ -d "$PROD" ]] || { echo "no production folder at $PROD" >&2; exit 1; }
command -v zstd >/dev/null || { echo "zstd is not installed" >&2; exit 1; }

if (( MEASURE )); then
  "$PY" -I "$HERE/public_bundle_lib.py" measure --mode "$MODE" --prod "$PROD"
  if [[ $MODE == full ]]; then
    "$PY" -I "$HERE/filter_passage_index.py" --prod "$PROD" --out /nonexistent --dry-run
  fi
  exit 0
fi

mkdir -p "$OUT"
WORK=$OUT/work.$$
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/stage"

# Run a heavy step under tess-job, waiting while the budget is taken (exit 3 = refused).
heavy() {  # cap name command...
  local cap=$1 name=$2; shift 2
  while true; do
    "$HOME/bin/tess-job" --fg "$name" "$cap" "$@"
    local rc=$?
    if [[ $rc -eq 3 ]]; then
      echo "$(date '+%F %T') tess-job refused $name, trying again in two minutes"
      sleep 120
    else
      return $rc
    fi
  done
}

START=$(date +%s)
STAMP=$(date +%Y%m%d)
EXTRA=()
if [[ $MODE == full ]]; then
  echo "== filtering the passage index to the bundled languages"
  heavy 10 public-bundle-filter nice -n 19 ionice -c3 "$PY" -I "$HERE/filter_passage_index.py" \
    --prod "$PROD" --out "$WORK/stage" || { echo "filter step failed" >&2; exit 1; }
  while IFS= read -r -d '' f; do
    EXTRA+=(--extra "${f#"$WORK/stage/"}=passage_index")
  done < <(find "$WORK/stage/data/passage_index" "$WORK/stage/cache/connections_map" -type f -print0 2>/dev/null)
fi

echo "== planning: selecting files, checking licences, hashing for the manifest"
heavy 4 public-bundle-plan nice -n 19 ionice -c3 "$PY" -I "$HERE/public_bundle_lib.py" plan \
  --mode "$MODE" --prod "$PROD" --work "$WORK" "${EXTRA[@]}" || { echo "plan step failed" >&2; exit 1; }

DEST=$OUT/tesserae-public-$MODE-$STAMP.tar.zst
echo "== writing $DEST"
heavy 4 public-bundle-tar nice -n 19 ionice -c3 "$SELF" --_tar "$WORK" "$PROD" "$DEST" || { echo "archive step failed" >&2; exit 1; }

cp "$WORK/stage/MANIFEST.tsv" "$OUT/MANIFEST-$MODE-$STAMP.tsv"
cp "$WORK/stage/LICENSES.md" "$OUT/LICENSES-$MODE-$STAMP.md"
( cd "$OUT" && sha256sum "$(basename "$DEST")" > "$(basename "$DEST").sha256" )
zstd -t -q "$DEST" || { echo "archive does not pass zstd -t" >&2; exit 1; }
END=$(date +%s)
echo "done: $(du -h "$DEST" | cut -f1) in $(( END - START )) seconds -> $DEST"
