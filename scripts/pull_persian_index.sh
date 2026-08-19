#!/bin/bash
# Marvin-side: pull the GPU-built Persian index from the private HF dataset and
# unpack it into the deploy tree. Run after the GPU job prints "UPLOADED".
#   HF_TOKEN=hf_xxx HF_DATASET=user/tesserae-motif-embeddings DEST=<repo> bash scripts/pull_persian_index.sh
set -euo pipefail
HF_DATASET="${HF_DATASET:?set HF_DATASET to the dataset id}"
: "${HF_TOKEN:?set HF_TOKEN (read access)}"
DEST="${DEST:?set DEST to the target repo root (e.g. /home/ncoffee/tesserae-persian)}"
VENV=/home/ncoffee/venv_embed/bin/python
TMP="$(mktemp -d)"

$VENV - "$HF_TOKEN" "$HF_DATASET" "$TMP" <<'PY'
import sys
from huggingface_hub import hf_hub_download
tok, ds, tmp = sys.argv[1], sys.argv[2], sys.argv[3]
print(hf_hub_download(repo_id=ds, repo_type="dataset",
                      filename="persian_index.tar.zst", token=tok, local_dir=tmp))
PY
tar --use-compress-program='zstd -d' -xf "$TMP/persian_index.tar.zst" -C "$DEST"
echo "fa_index.db: $(ls -lh "$DEST/data/inverted_index/fa_index.db" | awk '{print $5}')"
rm -rf "$TMP"
echo "DONE."
