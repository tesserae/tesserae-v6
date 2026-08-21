#!/usr/bin/env python3
"""Recompute Hebrew line embeddings with the shipped SentenceTransformer model.

Mirrors the query-time path (semantic_similarity.encode_texts -> model.encode),
so stored and query embeddings share one space. Output matches the existing
format: backend/embeddings/he/<base>.npy + <base>.meta.json.

Run:  venv/bin/python scripts/recompute_hebrew_embeddings.py
"""
import json, os, re, sys
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTS_DIR = os.path.join(PROJECT_ROOT, 'texts', 'he')
EMB_DIR = os.path.join(PROJECT_ROOT, 'backend', 'embeddings', 'he')
MODEL_DIR = os.path.join(PROJECT_ROOT, 'backend', 'models', 'miqrabert-hebrew-thematic')
MODEL_NAME = 'miqrabert-hebrew-thematic'

def main():
    from sentence_transformers import SentenceTransformer
    os.makedirs(EMB_DIR, exist_ok=True)
    print(f"Loading {MODEL_DIR} ...", flush=True)
    model = SentenceTransformer(MODEL_DIR)
    tess = sorted(f for f in os.listdir(TEXTS_DIR) if f.endswith('.tess'))
    print(f"Hebrew texts: {len(tess)}", flush=True)
    total = 0
    for tf in tess:
        base = tf[:-5]
        lines = []
        with open(os.path.join(TEXTS_DIR, tf), encoding='utf-8') as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                m = re.match(r'^<([^>]+)>\t(.+)$', ln)
                if m:
                    lines.append(m.group(2))
        if not lines:
            continue
        emb = model.encode(lines, batch_size=64, show_progress_bar=False).astype(np.float32)
        np.save(os.path.join(EMB_DIR, f'{base}.npy'), emb)
        with open(os.path.join(EMB_DIR, f'{base}.meta.json'), 'w') as f:
            json.dump({'text_file': tf, 'n_lines': len(lines),
                       'embedding_dim': int(emb.shape[1]),
                       'model': MODEL_NAME, 'method': 'sentence_transformer'}, f, indent=2)
        total += len(lines)
        print(f"  {base}: {emb.shape}", flush=True)
    print(f"Done. {len(tess)} files, {total} lines.", flush=True)

if __name__ == '__main__':
    main()
