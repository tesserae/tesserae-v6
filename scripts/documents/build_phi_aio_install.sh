#!/bin/bash
# Rebuild the Greek documents index and metadata.db copies for the Attic Inscriptions Online
# documents whose Greek is PHI's (every PHI record of an inscription, in AIO's order), into an
# install folder with SHA256SUMS.txt. Run again whenever more PHI records have been fetched.
# Works on copies only, never writes under /var/www. The PHI records are licensed text and stay
# outside the repository (default ~/licensed_text/phi_greek_aio/raw).
#
# usage: build_phi_aio_install.sh [INSTALL_DIR]      (default ~/tesserae-backups/phi_aio_2026-10-22/install2)
# needs under $W: aio/{raw,html,phi_needed.json}, build/texts_combined/grc (the 104 non-AIO .tess files
# plus the previous aio__attica.tess, which is replaced), and ~/tesserae-backups/aio_2026-10-20/bbaw_*.
set -e -o pipefail
W=${PHI_AIO_WORK:-$HOME/tesserae-backups/phi_aio_2026-10-22}
PHI_RAW=${PHI_RAW:-$HOME/licensed_text/phi_greek_aio/raw}
OUT=${1:-$W/install2}
SCRIPTS=$(cd "$(dirname "$0")" && pwd)
PY=${PY:-/home/ncoffee/tesserae-v6-dev/venv/bin/python}
B=$W/build2
JOB="$HOME/bin/tess-job --wait --fg phiaio"
df -h / | tail -1
rm -rf "$B"; mkdir -p "$B/index_out" "$B/restored/grc" "$OUT"
$JOB 2 $PY -I $SCRIPTS/aio_convert.py $W/aio/raw $W/aio/html $B/aio.jsonl --report $B/convert_report.json \
  --bbaw-dir $HOME/tesserae-backups/aio_2026-10-20 --phi-dir "$PHI_RAW" --phi-list $W/aio/phi_needed.json | tail -1 | cut -c1-120
$JOB 3 $PY -I $SCRIPTS/write_document_tess.py --input $B/aio.jsonl --output-root $B/texts_aio --all-short --summary-out $B/write_tess_summary.json | tail -1
mkdir -p $B/texts_combined; cp -r $W/build/texts_combined/grc $B/texts_combined/
cp $B/texts_aio/grc/aio__attica.tess $B/texts_aio/grc/aio__attica.restored_words.jsonl $B/texts_combined/grc/
cp $B/texts_aio/grc/aio__attica.restored_words.jsonl $B/restored/grc/
$JOB 10 $PY -I $SCRIPTS/build_documents_index.py --language grc --texts-root $B/texts_combined --index-dir $B/index_out \
  --cache-root $B/cache --scratch-root $B/scratch --skip-cache --quiet --summary-out $B/build_summary.json | tail -1
cp /var/www/tesseraev6_flask/data/documents/metadata.db $B/metadata.db
$JOB 3 $PY -I $SCRIPTS/aio_metadata.py $B/aio.jsonl $B/metadata.db --tess $B/texts_aio/grc/aio__attica.tess | tail -1 | cut -c1-160
cp $B/index_out/grc_documents_index.db $B/metadata.db $B/texts_aio/grc/aio__attica.restored_words.jsonl "$OUT"/
(cd "$OUT" && sha256sum aio__attica.restored_words.jsonl grc_documents_index.db metadata.db > SHA256SUMS.txt && sha256sum -c SHA256SUMS.txt)
chmod -R go-rwx "$B"
