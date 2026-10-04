#!/usr/bin/env python3
"""Offline, read-only measurement: do the new passage descriptions (replaced
2026-10-03) retrieve the pilot gold set better than the old ones, using
vectors that already exist on disk.

No server call except the local query encoder (POST /embed). No write to
any production path. The passage-index embeddings and metadata are opened
with numpy mmap_mode='r' or read as plain files; nothing under
/var/www is modified.

Inputs (all read-only, all outside this repository):
  - the live passage-index vectors:
      /var/www/tesseraev6_flask/data/passage_index/embeddings.npy
    and the pre-2026-10-03 backup, same row order, same ids:
      /var/www/tesseraev6_flask/data/passage_index/embeddings.npy.bak-glm-20261003-2330
  - the shared id list (unchanged between the two):
      /var/www/tesseraev6_flask/data/passage_index/ids.json
  - window metadata (language, work, ref_start, ref_end) for every id, read
    from the CURRENT descriptions.jsonl. A spot check against the pre-2026-
    10-03 backup descriptions file confirmed these four fields are identical
    across the swap for a sampled id: only the generated text (and its
    vector) changed, not the window's place in the corpus.
  - the pilot gold set and its matching rule. These live in this machine's
    evaluation/theme_benchmark/ working directory, which is covered by this
    repository's own .gitignore (see the comment above that entry) and has
    never had a file committed to it. This script does not embed the gold
    set's content and does not commit it. It reads pilot_gold.json from a
    path given by TESSERAE_GOLD_DIR (defaulting to the sibling checkout
    path below, since that is where this machine keeps it) and vendors the
    ~30-line, non-sensitive overlap-matching routine from score_common.py
    inline below, so this script carries no import dependency on a
    directory that is not part of the repository.

Method:
  For each motif in the gold set, and for each of its query forms that is
  not null (query_generic always, query_named when present), the query text
  is embedded once ("query: " prefix, per Theme Search convention). Cosine
  similarity against a unit-length embedding is a plain dot product, so the
  query vector is scored against the full embeddings matrix in row blocks
  of 50,000 (about 100 MB per block at float32), keeping peak memory well
  under the job's 4 GB cap. This is done once per (query form, old/new
  matrix), producing one score per window; three different top-100 lists
  are then read off that same score vector:
    - all: the top 100 scores over the whole matrix.
    - native: the top 100 scores restricted to windows whose language is
      the motif's single instance language (if the motif's instances span
      more than one language, this condition falls back to 'all', the same
      rule score_theme_search.py uses for its native-language run).
    - gold_works: the 'all' top-100 list, filtered down to windows whose
      work is one of the motif's gold works. This mirrors score_theme_
      search.py's "known-item" variant, which filters the saved top-100
      rather than re-ranking a restricted pool.
  A gold instance counts as hit at rank r if some candidate at rank <= r
  has the same normalized work and an overlapping (unit, line) span. This
  is the exact rule in score_common.py's hits_instance / score_motif,
  reproduced verbatim below.
"""
import json
import os
import re
import sys
import time
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PASSAGE_DIR = '/var/www/tesseraev6_flask/data/passage_index'
IDS_PATH = os.path.join(PASSAGE_DIR, 'ids.json')
NEW_EMB_PATH = os.path.join(PASSAGE_DIR, 'embeddings.npy')
OLD_EMB_PATH = os.path.join(PASSAGE_DIR, 'embeddings.npy.bak-glm-20261003-2330')
DESC_PATH = os.path.join(PASSAGE_DIR, 'descriptions.jsonl')
EMBED_URL = 'http://127.0.0.1:8090/embed'
BLOCK = 50_000
CUTOFFS = [10, 50, 100]
TOPK = 100

GOLD_DIR = os.environ.get(
    'TESSERAE_GOLD_DIR',
    '/home/ncoffee/tesserae-v6-dev/evaluation/theme_benchmark',
)
GOLD_PATH = os.path.join(GOLD_DIR, 'pilot_gold.json')

OUT_DIR = os.path.join(HERE, 'runs', 'offline_gold_recall')
OUT_PATH = os.path.join(OUT_DIR, 'results.json')


# ---- vendored matching rule (score_common.py, verbatim logic) ----
def norm_work(w):
    w = str(w or '').lower().replace('.tess', '')
    w = re.sub(r'\.part\.\d+.*$', '', w)
    return w


def ref_nums(ref):
    nums = re.findall(r'\d+', str(ref or ''))
    if not nums:
        return None, None
    if len(nums) == 1:
        return None, int(nums[0])
    return int(nums[-2]), int(nums[-1])


def window_span_from_meta(work, ref_start, ref_end):
    w = norm_work(work)
    u1, l1 = ref_nums(ref_start)
    u2, l2 = ref_nums(ref_end)
    return w, u1, l1, u2, l2


def hits_instance(inst, span):
    w, u1, l1, u2, l2 = span
    if w != norm_work(inst['work_id']):
        return False
    unit, s, e = inst['unit'], inst['start'], inst['end']
    if s is None:
        return u1 == unit or u2 == unit
    if u1 is None:
        return False
    lo = (u1, l1 if l1 is not None else 0)
    hi = (u2 if u2 is not None else u1, l2 if l2 is not None else 10 ** 6)
    return not (hi < (unit, s) or lo > (unit, e))


def score_motif(instances, ranked_spans):
    found_at = {}
    for idx, span in enumerate(ranked_spans, start=1):
        for j, inst in enumerate(instances):
            if j in found_at:
                continue
            if hits_instance(inst, span):
                found_at[j] = idx
    out = {}
    for k in CUTOFFS:
        out[f'r@{k}'] = sum(1 for r in found_at.values() if r <= k)
    out['n_gold'] = len(instances)
    out['ranks'] = sorted(found_at.values())
    return out
# ---- end vendored rule ----


def load_metadata(ids):
    """id -> (language, span tuple) for every row, aligned to `ids` order."""
    by_id = {}
    with open(DESC_PATH) as f:
        for line in f:
            r = json.loads(line)
            by_id[r['id']] = (r.get('language'), r.get('work'),
                               r.get('ref_start'), r.get('ref_end'))
    languages = []
    spans = []
    works = []
    missing = 0
    for _id in ids:
        rec = by_id.get(_id)
        if rec is None:
            missing += 1
            languages.append(None)
            spans.append(('', None, None, None, None))
            works.append('')
            continue
        lang, work, rs, re_ = rec
        languages.append(lang)
        span = window_span_from_meta(work, rs, re_)
        spans.append(span)
        works.append(span[0])
    if missing:
        print(f"WARNING: {missing} ids in ids.json had no descriptions.jsonl "
              f"row; treated as unmatched.", file=sys.stderr)
    return languages, spans, works


def embed_queries(texts):
    payload = json.dumps({'texts': [f'query: {t}' for t in texts]}).encode()
    req = urllib.request.Request(
        EMBED_URL, data=payload,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    vecs = np.array(data['vectors'], dtype=np.float32)
    return vecs


def compute_scores(emb_path, qvec, n_rows):
    arr = np.load(emb_path, mmap_mode='r')
    assert arr.shape[0] == n_rows, (emb_path, arr.shape, n_rows)
    scores = np.empty(n_rows, dtype=np.float32)
    for start in range(0, n_rows, BLOCK):
        end = min(start + BLOCK, n_rows)
        chunk = arr[start:end].astype(np.float32)
        scores[start:end] = chunk @ qvec
    return scores


def top_indices(scores, k, pool=None):
    if pool is not None:
        if len(pool) == 0:
            return np.array([], dtype=np.int64)
        sub = scores[pool]
        kk = min(k, len(pool))
        part = np.argpartition(sub, -kk)[-kk:]
        order = part[np.argsort(-sub[part])]
        return pool[order]
    kk = min(k, len(scores))
    part = np.argpartition(scores, -kk)[-kk:]
    order = part[np.argsort(-scores[part])]
    return order


def ranked_spans_for(indices, spans):
    return [spans[i] for i in indices]


def main():
    t0 = time.time()
    peak_note = ("peak RSS is reported by /usr/bin/time around the whole "
                  "process in the wrapper that invokes this script")

    gold = json.load(open(GOLD_PATH))
    ids = json.load(open(IDS_PATH))
    n_rows = len(ids)
    languages, spans, works = load_metadata(ids)
    languages = np.array(languages, dtype=object)
    works_arr = np.array(works, dtype=object)

    # index pools by language, built once
    lang_pool = {}
    for lg in set(languages.tolist()):
        if lg is None:
            continue
        lang_pool[lg] = np.where(languages == lg)[0]

    # Build the list of (motif, form_label, query_text) to run.
    jobs = []
    for m in gold:
        jobs.append((m, 'generic', m['query_generic']))
        if m.get('query_named'):
            jobs.append((m, 'named', m['query_named']))

    query_texts = [qt for _, _, qt in jobs]
    print(f"Embedding {len(query_texts)} query forms from {len(gold)} motifs...")
    qvecs = embed_queries(query_texts)
    print(f"Got {qvecs.shape} vectors from the encoder.")

    per_motif_rows = []
    totals = {
        cond: {f'r@{k}': {'old': 0, 'new': 0} for k in CUTOFFS}
        for cond in ('all', 'native', 'gold_works')
    }
    n_gold_total = {'all': 0, 'native': 0, 'gold_works': 0}

    for (m, form_label, qtext), qvec in zip(jobs, qvecs):
        motif = m['motif']
        instances = m['instances']
        inst_langs = sorted(set(i['language'] for i in instances))
        native_lang = inst_langs[0] if len(inst_langs) == 1 else None
        gold_works = set(norm_work(i['work_id']) for i in instances)

        # The query text itself is not stored in the result file: it is a
        # paraphrase of the gold motif, and the private pilot_gold.json
        # (never committed) is the place for that, not a file in this PR.
        row = {'motif': motif, 'form': form_label,
               'n_gold': len(instances), 'instance_languages': inst_langs,
               'conditions': {}}

        for side, path in (('old', OLD_EMB_PATH), ('new', NEW_EMB_PATH)):
            scores = compute_scores(path, qvec, n_rows)

            # all
            idx_all = top_indices(scores, TOPK)
            s_all = score_motif(instances, ranked_spans_for(idx_all, spans))

            # native (restrict candidate pool before ranking; fall back to
            # 'all' when the motif's instances span more than one language,
            # same rule score_theme_search.py uses)
            if native_lang is not None and native_lang in lang_pool:
                idx_native = top_indices(scores, TOPK, pool=lang_pool[native_lang])
            else:
                idx_native = idx_all
            s_native = score_motif(instances, ranked_spans_for(idx_native, spans))

            # gold_works: filter the 'all' top-100 post hoc, same as
            # score_theme_search.py's known-item variant
            kept = [i for i in idx_all if works_arr[i] in gold_works]
            s_gw = score_motif(instances, ranked_spans_for(kept, spans))

            for cond, s in (('all', s_all), ('native', s_native), ('gold_works', s_gw)):
                row['conditions'].setdefault(cond, {})[side] = s
                for k in CUTOFFS:
                    totals[cond][f'r@{k}'][side] += s[f'r@{k}']

        for cond in ('all', 'native', 'gold_works'):
            n_gold_total[cond] += row['n_gold']

        per_motif_rows.append(row)
        print(f"{motif:24s} {form_label:8s} gold={len(instances):2d}  "
              f"all old/new r@10={row['conditions']['all']['old']['r@10']}/"
              f"{row['conditions']['all']['new']['r@10']}  "
              f"r@100={row['conditions']['all']['old']['r@100']}/"
              f"{row['conditions']['all']['new']['r@100']}",
              flush=True)

    elapsed = time.time() - t0
    result = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S %z'),
        'files': {
            'new_embeddings': NEW_EMB_PATH,
            'old_embeddings': OLD_EMB_PATH,
            'ids': IDS_PATH,
            'descriptions_for_metadata': DESC_PATH,
            'gold_path': GOLD_PATH,
        },
        'n_rows': n_rows,
        'n_query_forms': len(jobs),
        'n_motifs': len(gold),
        'elapsed_seconds': elapsed,
        'per_motif': per_motif_rows,
        'totals': totals,
        'n_gold_total': n_gold_total,
        'note': peak_note,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, 'w') as f:
        json.dump(result, f, indent=2, default=lambda o: list(o) if isinstance(o, np.ndarray) else o)

    print()
    print(f"{'condition':12s} {'gold':>5s}  {'r@10 old':>9s} {'r@10 new':>9s}  "
          f"{'r@50 old':>9s} {'r@50 new':>9s}  {'r@100 old':>10s} {'r@100 new':>10s}")
    for cond in ('all', 'native', 'gold_works'):
        t = totals[cond]
        n = n_gold_total[cond]
        print(f"{cond:12s} {n:5d}  "
              f"{t['r@10']['old']:9d} {t['r@10']['new']:9d}  "
              f"{t['r@50']['old']:9d} {t['r@50']['new']:9d}  "
              f"{t['r@100']['old']:10d} {t['r@100']['new']:10d}")
    print()
    print(f"elapsed: {elapsed:.1f}s, {len(jobs)} query forms over {n_rows} windows")
    print(f"results written to {OUT_PATH}")


if __name__ == '__main__':
    main()
