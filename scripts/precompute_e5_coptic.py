"""Pre-compute multilingual-e5-large embeddings for the Coptic corpus.

Outputs one .npy + one .meta.json per .tess file into
backend/embeddings_e5/cop/, mirroring the existing Latin schema in
backend/embeddings_e5/la/.

multilingual-e5-large supports 100+ languages including Coptic via its
XLM-RoBERTa base. The model expects "passage: " prefix on inputs.
"""
import os
import sys
import json
import time
import re
import numpy as np
from datetime import datetime

sys.path.insert(0, '/home/ncoffee/tesserae-v6-dev')

MODEL_NAME = 'intfloat/multilingual-e5-large'
TEXTS_DIR = '/home/ncoffee/tesserae-v6-dev/texts/cop'
OUT_DIR = '/home/ncoffee/tesserae-v6-dev/backend/embeddings_e5/cop'
PREFIX = 'passage: '


def parse_tess(path):
    """Read a .tess file. Each line: <ref> <tab> text. Returns (refs, texts)."""
    refs, texts = [], []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line:
                continue
            m = re.match(r'^<([^>]+)>\t(.*)$', line)
            if not m:
                continue
            refs.append(m.group(1).strip())
            texts.append(m.group(2).strip())
    return refs, texts


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    from sentence_transformers import SentenceTransformer

    print(f"[setup] loading {MODEL_NAME}")
    t0 = time.time()
    model = SentenceTransformer(MODEL_NAME)
    print(f"[setup] model loaded in {time.time()-t0:.1f}s")

    files = sorted(f for f in os.listdir(TEXTS_DIR) if f.endswith('.tess'))
    print(f"[setup] {len(files)} Coptic .tess files to process")

    start = time.time()
    total_lines = 0

    for i, fname in enumerate(files, 1):
        stem = fname[:-len('.tess')]
        out_npy = os.path.join(OUT_DIR, f'{stem}.npy')
        out_meta = os.path.join(OUT_DIR, f'{stem}.meta.json')
        if os.path.exists(out_npy) and os.path.exists(out_meta):
            print(f"[{i:3}/{len(files)}] {stem}: already done, skipping")
            continue

        path = os.path.join(TEXTS_DIR, fname)
        refs, texts = parse_tess(path)
        if not texts:
            print(f"[{i:3}/{len(files)}] {stem}: empty, skipping")
            continue

        prefixed = [PREFIX + t for t in texts]
        t1 = time.time()
        embeddings = model.encode(prefixed, batch_size=32, show_progress_bar=False,
                                   normalize_embeddings=False)
        elapsed = time.time() - t1
        rate = len(texts) / max(0.01, elapsed)
        total_lines += len(texts)
        cumulative = time.time() - start

        np.save(out_npy, embeddings.astype(np.float32))
        with open(out_meta, 'w', encoding='utf-8') as f:
            json.dump({
                'text_path': path,
                'language': 'cop',
                'n_lines': len(texts),
                'embedding_dim': int(embeddings.shape[1]),
                'model': MODEL_NAME,
                'prefix': PREFIX,
                'created': datetime.now().isoformat(),
                'line_refs': refs,
            }, f, indent=2)

        print(f"[{i:3}/{len(files)}] {stem}: {len(texts):5} lines in {elapsed:5.1f}s "
              f"({rate:5.0f} lines/s); cumulative {total_lines:6} lines in {cumulative/60:.1f}min")

    print(f"\n[done] {total_lines} total lines embedded in {(time.time()-start)/60:.1f} min")


if __name__ == '__main__':
    main()
