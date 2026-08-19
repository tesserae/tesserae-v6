#!/bin/bash
# Build the Persian (fa) inverted index on a RENTED GPU pod, using GPU-accelerated
# Stanza. ~18h on CPU -> ~1-2h on the A40. Uploads fa_index.db to a private HF
# dataset for Marvin to pull back. Run this AFTER the motif embed + text top-up.
#
#   HF_TOKEN=hf_xxxx bash <(curl -sSL <this-gist-raw-url>)
set -euo pipefail
REPO_URL="${REPO_URL:-https://github.com/tesserae/tesserae-v6.git}"
REPO_BRANCH="${REPO_BRANCH:-feature/persian-ship}"
HF_DATASET="${HF_DATASET:-tesserae-motif-embeddings}"   # reuse the motif dataset by default
WORK="${WORK:-/workspace/persian}"

echo "== 0. checks =="
: "${HF_TOKEN:?set HF_TOKEN to a HuggingFace WRITE token}"
python -c "import torch; assert torch.cuda.is_available(), 'no CUDA GPU visible'; print('GPU:', torch.cuda.get_device_name(0))"

echo "== 1. deps =="
pip install -q --upgrade stanza "huggingface_hub>=0.24"

echo "== 2. clone the Persian branch (has backend/persian, texts/fa, builder) =="
mkdir -p "$WORK" && cd "$WORK"
if [ -d repo ]; then
  git -C repo fetch --depth 1 origin "$REPO_BRANCH" && git -C repo reset --hard FETCH_HEAD
else
  git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" repo
fi
cd repo

echo "== 3. download the Stanza Persian model =="
python -c "import stanza; stanza.download('fa')"

echo "== 4. build the fa index on GPU (all 23 texts, 936K verses) =="
export TESSERAE_STANZA_GPU=1 PYTHONPATH="$PWD"
python scripts/build_inverted_index.py --language fa

echo "== 5. package (index + any lemma/frequency caches) =="
cd "$WORK/repo"
TARBALL="$WORK/persian_index.tar.zst"
command -v zstd >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq zstd || true; }
tar --use-compress-program='zstd -3 -T0' -cf "$TARBALL" \
    data/inverted_index/fa_index.db \
    $( [ -d cache/lemmas/fa ] && echo cache/lemmas/fa ) \
    $( ls cache/frequencies/fa.json 2>/dev/null || true )
ls -lh "$TARBALL"

echo "== 6. upload to HuggingFace =="
python - "$HF_TOKEN" "$HF_DATASET" "$TARBALL" <<'UP_EOF'
import sys
from huggingface_hub import HfApi, whoami
token, dataset, tarball = sys.argv[1], sys.argv[2], sys.argv[3]
api = HfApi(token=token)
if "/" not in dataset:
    dataset = f"{whoami(token=token)['name']}/{dataset}"
api.create_repo(dataset, repo_type="dataset", private=True, exist_ok=True)
api.upload_file(path_or_fileobj=tarball, path_in_repo="persian_index.tar.zst",
                repo_id=dataset, repo_type="dataset")
print("UPLOADED ->", dataset)
UP_EOF
echo "== DONE. Tell Neil; Claude pulls persian_index.tar.zst onto Marvin. =="
