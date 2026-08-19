#!/bin/bash
# Build a plugin language's inverted index on a RENTED GPU pod using GPU Stanza.
# Generic: set LANG (ur|he|ar|fa|cop) and REPO_BRANCH. Uploads <LANG>_index.tar.zst.
#
#   LANG=ur HF_TOKEN=hf_xxx bash <(curl -sSL <this-gist-raw-url>)
set -euo pipefail
: "${LANG:?set LANG to a language code (ur|he|ar|fa)}"
REPO_URL="${REPO_URL:-https://github.com/tesserae/tesserae-v6.git}"
REPO_BRANCH="${REPO_BRANCH:-feature/multilang-ship}"
HF_DATASET="${HF_DATASET:-tesserae-motif-embeddings}"
WORK="${WORK:-/workspace/idx_$LANG}"
# Stanza uses the same code except Persian's model id is 'fa'; map if needed.
STANZA_LANG="${STANZA_LANG:-$LANG}"

echo "== 0. checks =="
: "${HF_TOKEN:?set HF_TOKEN to a HuggingFace WRITE token}"
python -c "import torch; assert torch.cuda.is_available(), 'no CUDA GPU visible'; print('GPU:', torch.cuda.get_device_name(0))"

echo "== 1. deps =="
command -v zstd >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq zstd || true; }
pip install -q --upgrade stanza "huggingface_hub>=0.24"

echo "== 2. clone branch $REPO_BRANCH =="
mkdir -p "$WORK" && cd "$WORK"
if [ -d repo ]; then
  git -C repo fetch --depth 1 origin "$REPO_BRANCH" && git -C repo reset --hard FETCH_HEAD
else
  git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" repo
fi
cd repo

echo "== 3. download Stanza model ($STANZA_LANG) =="
python -c "import stanza; stanza.download('$STANZA_LANG')"

echo "== 4. build $LANG index on GPU =="
export TESSERAE_STANZA_GPU=1 PYTHONPATH="$PWD"
python scripts/build_inverted_index.py --language "$LANG"

echo "== 5. package =="
cd "$WORK/repo"
TARBALL="$WORK/${LANG}_index.tar.zst"
tar --use-compress-program='zstd -3 -T0' -cf "$TARBALL" \
    "data/inverted_index/${LANG}_index.db" \
    $( [ -d "cache/lemmas/$LANG" ] && echo "cache/lemmas/$LANG" ) \
    $( ls "cache/frequencies/$LANG.json" 2>/dev/null || true )
ls -lh "$TARBALL"

echo "== 6. upload =="
python - "$HF_TOKEN" "$HF_DATASET" "$TARBALL" "${LANG}_index.tar.zst" <<'UP_EOF'
import sys
from huggingface_hub import HfApi, whoami
token, dataset, tarball, name = sys.argv[1:5]
api = HfApi(token=token)
if "/" not in dataset:
    dataset = f"{whoami(token=token)['name']}/{dataset}"
api.create_repo(dataset, repo_type="dataset", private=True, exist_ok=True)
api.upload_file(path_or_fileobj=tarball, path_in_repo=name, repo_id=dataset, repo_type="dataset")
print("UPLOADED ->", dataset, name)
UP_EOF
echo "== DONE ($LANG). =="
