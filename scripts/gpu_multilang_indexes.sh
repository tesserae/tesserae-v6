#!/bin/bash
# Build Urdu + Hebrew + Arabic indexes in ONE run on the rented GPU pod.
# Clones the multilang branch once, then builds/uploads each language's index
# (<lang>_index.tar.zst) with GPU Stanza. Corpora are tiny, so this is quick.
#
#   HF_TOKEN=hf_xxxx bash <(curl -sSL <this-gist-raw-url>)
set -euo pipefail
REPO_URL="${REPO_URL:-https://github.com/tesserae/tesserae-v6.git}"
REPO_BRANCH="${REPO_BRANCH:-feature/multilang-ship}"
HF_DATASET="${HF_DATASET:-tesserae-motif-embeddings}"
LANGS="${LANGS:-ur he ar}"
WORK="${WORK:-/workspace/multilang_idx}"

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
export TESSERAE_STANZA_GPU=1 PYTHONPATH="$PWD"

for LANG in $LANGS; do
  echo "======================= $LANG ======================="
  echo "-- download Stanza model ($LANG) --"
  python -c "import stanza; stanza.download('$LANG')"
  echo "-- build $LANG index on GPU --"
  python scripts/build_inverted_index.py --language "$LANG"
  echo "-- package + upload $LANG --"
  TARBALL="$WORK/${LANG}_index.tar.zst"
  tar --use-compress-program='zstd -3 -T0' -cf "$TARBALL" \
      "data/inverted_index/${LANG}_index.db" \
      $( [ -d "cache/lemmas/$LANG" ] && echo "cache/lemmas/$LANG" ) \
      $( ls "cache/frequencies/$LANG.json" 2>/dev/null || true )
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
done
echo "== ALL DONE (ur/he/ar). =="
