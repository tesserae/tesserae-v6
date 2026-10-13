#!/usr/bin/env python3
"""Precision and recall of backend.document_citations on the hand-labelled
sample tests/fixtures/doc_citations_sample200.json (200 windows drawn at random
by family from the documents collection's commentary and apparatus notes, the
literary commentaries and the historians notes; gold labelled by hand before
the recogniser was run on it). A recognised reference counts as correct when
its span overlaps a gold span. References touching a window edge, and spans the
labeller marked neutral (ambiguous or out of scope), are ignored.

    python scripts/documents/eval_doc_citations.py [-v]
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from backend.document_citations import find_document_citations  # noqa: E402


def spans(ctx, items):
    out, used = [], {}
    for g in items:
        i = ctx.find(g, used.get(g, 0))
        assert i >= 0, g
        used[g] = i + len(g)
        out.append((i, i + len(g)))
    return out


def evaluate(path=os.path.join(ROOT, 'tests', 'fixtures', 'doc_citations_sample200.json'), verbose=False):
    sample = json.load(open(path, encoding='utf-8'))
    tp = fp = fn = n_gold = 0
    fam = {}
    for r in sample:
        ctx = r['ctx']
        gold = [g for g in spans(ctx, r['gold']) if g[0] > 0 and g[1] < len(ctx)]
        n_gold += len(gold)
        neutral = spans(ctx, r['neutral'])
        preds = [c for c in find_document_citations(ctx) if c['start'] > 0 and c['end'] < len(ctx)]
        hit = set()
        for c in preds:
            ov = lambda s: c['start'] < s[1] and s[0] < c['end']
            gi = [i for i, s in enumerate(gold) if ov(s)]
            if gi:
                tp += 1
                hit.update(gi)
                fam.setdefault(c['family'], [0, 0])[0] += 1
            elif any(ov(s) for s in neutral):
                continue
            else:
                fp += 1
                fam.setdefault(c['family'], [0, 0])[1] += 1
                if verbose:
                    print('FP #%d %s %s' % (r['n'], c['surface'], c['key']))
        for i, s in enumerate(gold):
            if i not in hit:
                fn += 1
                if verbose:
                    print('FN #%d %s' % (r['n'], ctx[s[0]:s[1]]))
    gold_n = n_gold
    p = tp / float(tp + fp) if tp + fp else 0.0
    rc = (gold_n - fn) / float(gold_n)
    return {'gold': gold_n, 'predicted': tp + fp, 'tp': tp, 'fp': fp, 'fn': fn, 'precision': p, 'recall': rc, 'by_family': fam}


if __name__ == '__main__':
    for name in ('doc_citations_sample200.json', 'doc_citations_heldout.json'):
        res = evaluate(os.path.join(ROOT, 'tests', 'fixtures', name), verbose='-v' in sys.argv)
        print(name, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res.items()})
