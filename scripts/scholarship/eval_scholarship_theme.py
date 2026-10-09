"""Measure Theme Search style retrieval over the scholarship index against FTS5 keyword search.

Two steps, because relevance is judged by a person:

  run    python eval_scholarship_theme.py run --index DIR --out results.json
         runs the 15 queries both ways, writes the top 10 of each with text
  score  python eval_scholarship_theme.py score --results results.json --judgments j.json
         j.json maps query -> {window_id: 0|1|2}; prints P@10 and nDCG@10 per
         query, per group and overall, for each system

Confidence figures use the arithmetic of backend/passage_index.find_by_text
(baseline = median score, head lift = mean of top ten minus baseline,
coherence = mean pairwise cosine of the top 20). The fitted thresholds belong
to the 530,917-window index and are not applied here.
"""
import argparse
import json
import math
import os
import re
import sqlite3
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_scholarship_theme_index import E5_PREFIX, embed_batch  # noqa: E402

QUERIES = {
    'thematic': ['hospitality in Homer', 'the storm as a political image in Roman epic',
                 "Dido's curse and Hannibal", 'the golden age in Augustan poetry',
                 'fame and rumour personified'],
    'passage': ['the opening of the Aeneid and its Homeric models', "Achilles' shield and ekphrasis",
                'the gates of sleep', 'Catullus 64 and the wedding', 'Lucretius on Epicurus'],
    'technical': ['textual crux in Aeneid 2', 'metrical anomaly hiatus',
                  'manuscript variant readings Horace', 'etymological wordplay Ovid',
                  'scholia and ancient commentators'],
}
STOP = set('a an the of in on and or to for with as by at from is are was be its it their his her'.split())


def ndcg_at(rels, ideal, k=10):
    dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rels[:k]))
    idl = sum(r / math.log2(i + 2) for i, r in enumerate(sorted(ideal, reverse=True)[:k]))
    return dcg / idl if idl else 0.0


def fts_query(q):
    toks = [t for t in re.findall(r"[A-Za-z0-9]+", q.lower()) if t not in STOP]
    return ' OR '.join(toks)


def build_fts(texts_db, rows):
    con = sqlite3.connect(':memory:')
    con.execute("CREATE VIRTUAL TABLE f USING fts5(body, tokenize='porter unicode61')")
    con.executemany('INSERT INTO f(rowid, body) VALUES (?,?)', rows)
    return con


def run(a):
    idx = a.index
    ids = json.load(open(os.path.join(idx, 'ids.json')))
    emb = np.load(os.path.join(idx, 'embeddings.npy')).astype(np.float32)
    recs = {}
    for line in open(os.path.join(idx, 'descriptions.jsonl'), encoding='utf-8'):
        r = json.loads(line); recs[r['id']] = r
    rows = []
    for i, wid in enumerate(ids):
        r = recs[wid]
        work = r['work'].replace('.', ' ').replace('_', ' ')
        rows.append((i, f"{r['commentator']} {work} {r['ref_start']} {r['desc']['gist']}"))
    fts = build_fts(None, rows)
    out = []
    for group, qs in QUERIES.items():
        for q in qs:
            v = embed_batch([E5_PREFIX + q])[0]
            sc = emb @ v
            base = float(np.median(sc))
            top = np.argsort(-sc)[:20]
            head = float(np.sort(sc)[-10:].mean()) - base
            blk = emb[top]; sim = blk @ blk.T
            coh = float((sim.sum() - 20) / (20 * 19))
            dense = [{'id': ids[i], 'score': round(float(sc[i]), 4)} for i in top[:10]]
            kw = [{'id': ids[r[0]], 'score': round(-r[1], 3)} for r in
                  fts.execute('SELECT rowid, bm25(f) FROM f WHERE f MATCH ? ORDER BY bm25(f) LIMIT 10', (fts_query(q),))]
            out.append({'group': group, 'query': q, 'baseline': round(base, 4), 'head_lift': round(head, 4),
                        'coherence': round(coh, 4), 'dense': dense, 'keyword': kw})
    for o in out:
        for sysname in ('dense', 'keyword'):
            for h in o[sysname]:
                r = recs[h['id']]
                h.update(source=r['source'], work=r['work'], commentator=r['commentator'],
                         ref=r['ref_start'], text=r['desc']['gist'])
    json.dump(out, open(a.out, 'w'), indent=1, ensure_ascii=False)
    print('wrote', a.out)


def score(a):
    res = json.load(open(a.results))
    J = json.load(open(a.judgments))
    agg = {}
    per = []
    for o in res:
        j = J[o['query']]
        ideal = list(j.values())
        row = {'group': o['group'], 'query': o['query']}
        for s in ('dense', 'keyword'):
            rels = [j.get(h['id'], 0) for h in o[s]]
            row[s] = {'p10': sum(1 for r in rels if r > 0) / 10, 'ndcg': ndcg_at(rels, ideal)}
        per.append(row)
    print(f"{'query':55s} {'dense P@10':>10s} {'nDCG':>6s} {'kw P@10':>8s} {'nDCG':>6s}")
    for r in per:
        print(f"{r['query'][:55]:55s} {r['dense']['p10']:10.2f} {r['dense']['ndcg']:6.2f} {r['keyword']['p10']:8.2f} {r['keyword']['ndcg']:6.2f}")
    for g in ['thematic', 'passage', 'technical', None]:
        sub = [r for r in per if g is None or r['group'] == g]
        m = lambda s, k: sum(r[s][k] for r in sub) / len(sub)
        print(f"{(g or 'ALL'):55s} {m('dense','p10'):10.2f} {m('dense','ndcg'):6.2f} {m('keyword','p10'):8.2f} {m('keyword','ndcg'):6.2f}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    r = sp.add_parser('run'); r.add_argument('--index', required=True); r.add_argument('--out', required=True)
    s = sp.add_parser('score'); s.add_argument('--results', required=True); s.add_argument('--judgments', required=True)
    a = ap.parse_args()
    run(a) if a.cmd == 'run' else score(a)
