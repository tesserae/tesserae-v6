#!/bin/bash
# BONUS: build Persian (fa) MOTIF EMBEDDINGS with BGE-M3 on the rented GPU, giving
# Persian semantic + cross-lingual motif-search parity with the other languages.
# Separate from the fa lexical index (that's Stanza). Run after the other GPU jobs.
#
#   HF_TOKEN=hf_xxxx bash <(curl -sSL <this-gist-raw-url>)
set -euo pipefail
REPO_URL="${REPO_URL:-https://github.com/tesserae/tesserae-v6.git}"
REPO_BRANCH="${REPO_BRANCH:-feature/persian-ship}"
HF_DATASET="${HF_DATASET:-tesserae-motif-embeddings}"
WORK="${WORK:-/workspace/persian_motif}"

echo "== 0. checks =="
: "${HF_TOKEN:?set HF_TOKEN to a HuggingFace WRITE token}"
python -c "import torch; assert torch.cuda.is_available(), 'no CUDA GPU visible'; print('GPU:', torch.cuda.get_device_name(0))"

echo "== 1. deps =="
command -v zstd >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq zstd || true; }
pip install -q --upgrade "sentence-transformers>=3" "huggingface_hub>=0.24"

echo "== 2. clone the Persian branch (has texts/fa + the embed script) =="
mkdir -p "$WORK" && cd "$WORK"
if [ -d repo ]; then
  git -C repo fetch --depth 1 origin "$REPO_BRANCH" && git -C repo reset --hard FETCH_HEAD
else
  git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" repo
fi
cd repo

echo "== 3. embed Persian only, both scales, on GPU (BGE-M3) =="
export MOTIF_ONLINE=1 MOTIF_LANGS=fa MOTIF_ROOT="$PWD" MOTIF_OUT="$WORK/out"
mkdir -p "$MOTIF_OUT"
python scripts/motif_embed_corpus.py

echo "== 4. package =="
cd "$WORK"
TARBALL="$WORK/persian_motif.tar.zst"
tar --use-compress-program='zstd -3 -T0' -cf "$TARBALL" -C "$MOTIF_OUT" .
ls -lh "$TARBALL"

echo "== 5. upload to HuggingFace =="
python - "$HF_TOKEN" "$HF_DATASET" "$TARBALL" <<'UP_EOF'
import sys
from huggingface_hub import HfApi, whoami
token, dataset, tarball = sys.argv[1], sys.argv[2], sys.argv[3]
api = HfApi(token=token)
if "/" not in dataset:
    dataset = f"{whoami(token=token)['name']}/{dataset}"
api.create_repo(dataset, repo_type="dataset", private=True, exist_ok=True)
api.upload_file(path_or_fileobj=tarball, path_in_repo="persian_motif.tar.zst",
                repo_id=dataset, repo_type="dataset")
print("UPLOADED ->", dataset)
UP_EOF
echo "== DONE. persian_motif.tar.zst uploaded; Claude pulls it to Marvin. =="
