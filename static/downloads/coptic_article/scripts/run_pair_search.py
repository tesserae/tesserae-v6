"""Reproduce the ranked outputs in outputs/ on a Tesserae V6 checkout.

Runs the V6 fusion search with the shipped biblical_coptic weight profile on
one of the two article text pairs and writes a ranked JSONL matching the
released files (rank, source_ref, target_ref, fused_score, match_basis,
quotation run length).

Usage, from the root of a Tesserae V6 checkout with the Coptic corpus:
    python scripts/run_pair_search.py hebrews_psalms  --top 10000
    python scripts/run_pair_search.py romans_isaiah   --top 10000
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.getcwd())

from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.fusion import iter_fusion_search

PAIRS = {
    # source = the older, quoted text; target = the later, quoting text
    'hebrews_psalms': ('sahidic.psalms.tess', 'sahidica.hebrews.tess'),
    'romans_isaiah': ('sahidic.isaiah.tess', 'sahidica.romans.tess'),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pair', choices=sorted(PAIRS))
    ap.add_argument('--top', type=int, default=10000)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    source_id, target_id = PAIRS[args.pair]
    source_path = os.path.join('texts', 'cop', source_id)
    target_path = os.path.join('texts', 'cop', target_id)

    tp = TextProcessor()
    src = tp.process_file(source_path, language='cop')
    tgt = tp.process_file(target_path, language='cop')

    results = []
    for evt, data in iter_fusion_search(
            source_units=src, target_units=tgt,
            matcher=Matcher(), scorer=Scorer(),
            source_id=source_id, target_id=target_id,
            language='cop', mode='merged',
            max_results=args.top,
            source_path=source_path, target_path=target_path):
        if evt == 'complete':
            results = data.get('results', [])

    out = args.out or f'{args.pair}_ranked_{args.top}.jsonl'
    with open(out, 'w') as f:
        for i, r in enumerate(results[:args.top], 1):
            f.write(json.dumps({
                'rank': i,
                'source_ref': r.get('source_ref'),
                'target_ref': r.get('target_ref'),
                'fused_score': r.get('fused_score'),
                'match_basis': r.get('match_basis'),
                'qrun': r.get('quotation_run_length'),
            }) + '\n')
    print(f'wrote {out} ({min(len(results), args.top)} rows)')


if __name__ == '__main__':
    main()
