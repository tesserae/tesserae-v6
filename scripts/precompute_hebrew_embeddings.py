#!/usr/bin/env python3
"""
Pre-compute BEREL sentence embeddings for all Hebrew texts.

BEREL (dicta-il/BEREL) is a BERT model trained on Rabbinic Hebrew.
Since it's not a sentence encoder, we use mean pooling over token embeddings
to create sentence-level representations (same approach as SPhilBERTa).

Output: backend/embeddings/he/*.npy + *.meta.json
"""

import json
import os
import sys
import numpy as np
import torch
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

TEXTS_DIR = os.path.join(PROJECT_ROOT, 'texts', 'he')
EMBEDDINGS_DIR = os.path.join(PROJECT_ROOT, 'backend', 'embeddings', 'he')


def mean_pooling(model_output, attention_mask):
    """Mean pooling: average token embeddings, weighted by attention mask."""
    token_embeddings = model_output.last_hidden_state
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)


def main():
    from transformers import AutoModel, AutoTokenizer

    os.makedirs(EMBEDDINGS_DIR, exist_ok=True)

    print("Loading BEREL model...")
    tokenizer = AutoTokenizer.from_pretrained('dicta-il/BEREL')
    model = AutoModel.from_pretrained('dicta-il/BEREL')
    model.eval()
    print(f"BEREL loaded: {sum(p.numel() for p in model.parameters())/1e6:.0f}M params")

    tess_files = sorted(f for f in os.listdir(TEXTS_DIR) if f.endswith('.tess'))
    print(f"Hebrew texts to embed: {len(tess_files)}")

    for tess_file in tess_files:
        filepath = os.path.join(TEXTS_DIR, tess_file)
        base_name = tess_file.replace('.tess', '')

        # Read lines
        lines = []
        refs = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                import re
                m = re.match(r'^<([^>]+)>\t(.+)$', line)
                if m:
                    refs.append(m.group(1))
                    lines.append(m.group(2))

        if not lines:
            continue

        print(f"  {base_name}: {len(lines)} lines...", end='', flush=True)

        # Batch encode
        BATCH_SIZE = 32
        all_embeddings = []

        for i in range(0, len(lines), BATCH_SIZE):
            batch = lines[i:i+BATCH_SIZE]
            encoded = tokenizer(batch, padding=True, truncation=True, max_length=512, return_tensors='pt')

            with torch.no_grad():
                output = model(**encoded)

            embeddings = mean_pooling(output, encoded['attention_mask'])
            # Normalize
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            all_embeddings.append(embeddings.numpy())

        embeddings_array = np.vstack(all_embeddings)

        # Save
        npy_path = os.path.join(EMBEDDINGS_DIR, f'{base_name}.npy')
        np.save(npy_path, embeddings_array)

        meta = {
            'text_file': tess_file,
            'n_lines': len(lines),
            'embedding_dim': embeddings_array.shape[1],
            'model': 'dicta-il/BEREL',
            'method': 'mean_pooling',
        }
        meta_path = os.path.join(EMBEDDINGS_DIR, f'{base_name}.meta.json')
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2)

        print(f" {embeddings_array.shape}")

    print("\nDone!")


if __name__ == '__main__':
    main()
