"""Stage 1c: audit the entity lemma sets and measure the audit's fixes (2026-10-17).

    venv/bin/python scripts/audit_entity_lemmas.py --entities-json KEYS.json \
        --graded-dir research/entities --outdir research/entities

Builds the lemma matcher in memory (no store), writes lemma_set_audit.csv, and measures the
fixed graded pairs for the stage 1b table, for the table after the audit's fixes, and for
the capitalized-share threshold at 0.3, 0.5, 0.7 and 0.9. Run it inside `tess-job --fg NAME 8`.
"""
import argparse
import collections
import csv
import json
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend import entity_index as ei  # noqa: E402
from backend import entity_lemma as el  # noqa: E402
from backend import entity_lemma_audit as ela  # noqa: E402

GRADED = ['precision_60', 'precision_scope40_regraded', 'precision_holdout40', 'precision_lemma_holdout40']


def load_pairs(graded_dir):
    pairs = []
    for f in GRADED:
        for p in json.load(open(os.path.join(graded_dir, f + '.json'), encoding='utf-8'))['pairs']:
            pairs.append(dict(p, file=f))
    return pairs


def pair_kept(texts_cache, p, idx_of, tok2ents):
    text = texts_cache[p['window_id']]
    idx = idx_of[p['entity_id']]
    t2e = tok2ents[p['lang']]
    for m in ei.WORD.finditer(text):
        raw = m.group(0)
        es = t2e.get(ei._fold_tok(raw))
        if es and idx in es and el.is_cap(raw):
            return True
    return False


def evaluate(pairs, texts_cache, idx_of, tok2ents):
    res = {}
    for p in pairs:
        right = p['verdict'] == 'right'
        kept = pair_kept(texts_cache, p, idx_of, tok2ents)
        res[(p['file'], p['n'])] = (right, kept)
    return res


def summarize(res):
    def one(sel):
        c = collections.Counter()
        for (f, n), (right, kept) in res.items():
            if sel(f):
                c[('ck' if right else 'wk') if kept else ('cd' if right else 'wd')] += 1
        kept = c['ck'] + c['wk']
        return {'correct_kept': c['ck'], 'correct_dropped': c['cd'], 'wrong_kept': c['wk'],
                'wrong_dropped': c['wd'], 'kept': kept,
                'precision_on_kept': round(c['ck'] / kept, 4) if kept else None,
                'recall': round(c['ck'] / (c['ck'] + c['cd']), 4) if c['ck'] + c['cd'] else None}
    out = {'all': one(lambda f: True)}
    for g in GRADED:
        out[g] = one(lambda f, g=g: f == g)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entities-json', required=True)
    ap.add_argument('--passage-dir', default=os.path.join(ROOT, 'data', 'passage_index'))
    ap.add_argument('--graded-dir', required=True)
    ap.add_argument('--outdir', required=True)
    a = ap.parse_args()
    t0 = time.time()
    keys = json.load(open(a.entities_json, encoding='utf-8'))
    entities, _ = ei.merge_list_entities(keys)
    idx_of = {e['entity_id']: i for i, e in enumerate(entities)}
    ids = json.load(open(os.path.join(a.passage_dir, 'ids.json')))
    unit = ei.unit_windows(ids)
    del ids
    texts = sqlite3.connect(f"file:{os.path.join(a.passage_dir, 'window_texts.db')}?mode=ro", uri=True)
    types = el.count_types(texts, unit)
    resolver = el.Resolver()
    prep = el.prepare_lemmas(entities, types, resolver)
    print(f'prepared {time.time() - t0:.0f}s', flush=True)

    pairs = load_pairs(a.graded_dir)
    tcache = {}
    for p in pairs:
        if p['window_id'] not in tcache:
            tcache[p['window_id']] = texts.execute('select text from window_texts where id=?',
                                                   (p['window_id'],)).fetchone()[0]
    evals = {}
    # the stage 1b table, the table after the fixes, and the threshold curve both ways
    configs = [('before_1b', 0.5, False, False), ('fixes_drops_only', 0.5, True, False),
               ('after_1c', 0.5, True, True)]
    for thr in (0.3, 0.7, 0.9):
        configs.append((f'thr{thr}_no_fixes', thr, False, False))
        configs.append((f'thr{thr}_fixes', thr, True, True))
    detail = {}
    before_t2e = before_info = None
    for name, thr, fixes, ov in configs:
        t2e, info = el.assemble_matcher(entities, types, prep, threshold=thr, audit_fixes=fixes,
                                        overrides=ov, log=lambda *_: None)
        res = evaluate(pairs, tcache, idx_of, t2e)
        evals[name] = summarize(res)
        detail[name] = {f'{f}#{n}': kept for (f, n), (right, kept) in res.items()}
        if name == 'before_1b':
            before_t2e, before_info = t2e, info
        print(name, json.dumps(evals[name]['all']), flush=True)
    json.dump({'evals': evals, 'kept_by_pair': detail,
               'pairs': [{k: p[k] for k in ('file', 'n', 'window_id', 'entity_id', 'token', 'lang', 'verdict')}
                         for p in pairs]},
              open(os.path.join(a.outdir, 'stage1c_eval.json'), 'w'), ensure_ascii=False, indent=1)

    # credit scan on the stage 1b table: windows per (entity, language, lemma)
    type_lemma = before_info['type_lemma']
    credit = collections.Counter()
    ent_windows = collections.defaultdict(set)
    done = 0
    for wid, lang, text in texts.execute('select id, language, text from window_texts'):
        if wid not in unit or lang not in ei.LANGS:
            continue
        done += 1
        t2e = before_t2e[lang]
        seen = set()
        for m in ei.WORD.finditer(text):
            raw = m.group(0)
            f = ei._fold_tok(raw)
            es = t2e.get(f)
            if not es or not el.is_cap(raw):
                continue
            lem = type_lemma[lang][f]
            for i in es:
                seen.add((i, lem))
        for i, lem in seen:
            credit[(i, lang, lem)] += 1
            ent_windows[i].add(done)
    print(f'credit scan done {time.time() - t0:.0f}s', flush=True)
    ent_n = {i: len(w) for i, w in ent_windows.items()}
    del ent_windows

    cand = before_info['candidate_lemmas']
    props = ela.propose(entities, cand, before_info['stats'])
    holders = collections.defaultdict(set)
    for lang in ei.LANGS:
        for i, lems in cand[lang].items():
            for lem in lems:
                holders[(lang, lem)].add(i)
    top400 = {i for i, _ in collections.Counter(ent_n).most_common(400)}
    shared_ents = {i for (lang, lem), s in holders.items() if len(s) > 1 for i in s}
    chosen = top400 | shared_ents
    stats = before_info['stats']
    rows = []
    for (lang, i, lem), (action, why) in props.items():
        if i not in chosen:
            continue
        s = stats[lang][lem]
        share = el.cap_share_of(stats, lang, lem)
        e = entities[i]
        hs = sorted(holders[(lang, lem)] - {i})
        rows.append({
            'entity_id': e['entity_id'], 'label': e['label'], 'type': e['type'], 'language': lang,
            'lemma': lem, 'windows_from_lemma': credit.get((i, lang, lem), 0),
            'entity_windows': ent_n.get(i, 0), 'in_top400': int(i in top400),
            'cap_share_inner': round(share, 3), 'occurrences': s[0],
            'lower_case_occurrences': s[0] - s[1], 'lower_case_inner': s[2] - s[3],
            'also_common_word': int(s[0] - s[1] > 0),
            'suffix': (ela.suffix_of(lang, lem) if e['type'] == 'place' and not ela.exempt(e['entity_id'], lang, lem) else ''),
            'shared_with_n': len(hs), 'shared_with': '; '.join(entities[j]['label'] for j in hs[:6]),
            'action': action, 'reason': why})
    rows.sort(key=lambda r: (-r['entity_windows'], r['entity_id'], r['language'], r['lemma']))
    with open(os.path.join(a.outdir, 'lemma_set_audit.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summ = {'rows': len(rows), 'entities': len(chosen), 'top400': len(top400),
            'by_action': dict(collections.Counter(r['action'] for r in rows)),
            'by_action_reason': dict(collections.Counter(f"{r['action']}:{r['reason']}" for r in rows)),
            'windows_by_action_reason': {},
            'all_pairs_by_action_reason': dict(collections.Counter(f"{v[0]}:{v[1]}" for v in props.values())),
            'suffix_rows': sum(1 for r in rows if r['suffix']),
            'lemmas_total_pairs': len(props)}
    wr = collections.Counter()
    for (lang, i, lem), (action, why) in props.items():
        wr[f'{action}:{why}'] += credit.get((i, lang, lem), 0)
    summ['windows_by_action_reason'] = dict(wr)
    summ['dropped_by_language'] = dict(collections.Counter(
        f'{k[0]}:{v[1]}' for k, v in props.items() if v[0] == 'drop'))
    summ['seconds'] = round(time.time() - t0)
    json.dump(summ, open(os.path.join(a.outdir, 'stage1c_audit_summary.json'), 'w'), indent=1)
    json.dump([{'entity_id': entities[i]['entity_id'], 'label': entities[i]['label'], 'lang': lang, 'lemma': lem,
                'reason': v[1], 'windows': credit.get((i, lang, lem), 0)}
               for (lang, i, lem), v in props.items() if v[0] == 'drop'],
              open(os.path.join(a.outdir, 'stage1c_dropped_lemmas.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
