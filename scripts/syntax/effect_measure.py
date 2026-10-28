"""Run the default production fusion search on one pair with chosen syntax databases.

The databases are chosen by patching backend.fusion in this process; no file is replaced.
Writes a JSON file with the timing, the gold-standard recall and the top results.

  python scripts/syntax/effect_measure.py --root DEVTREE --label live|new --lang la \
      --source lucan.bellum_civile.part.1.tess --target vergil.aeneid.tess \
      --db-la PATH --db-grc PATH --gold lucan_vergil --out result.json
  python scripts/syntax/effect_measure.py ... --greek-bench --out result.json   # Apollonius 3 against Homer
"""
import argparse, json, os, re, sys, time
from collections import defaultdict

ap = argparse.ArgumentParser()
ap.add_argument('--root', required=True)
ap.add_argument('--label', required=True)
ap.add_argument('--lang', default='la')
ap.add_argument('--source')
ap.add_argument('--target')
ap.add_argument('--db-la', required=True)
ap.add_argument('--db-grc', required=True)
ap.add_argument('--gold', default='')
ap.add_argument('--greek-bench', action='store_true')
ap.add_argument('--keep', type=int, default=500)
ap.add_argument('--out', required=True)
a = ap.parse_args()
sys.path.insert(0, a.root)
sys.path.insert(0, os.path.join(a.root, 'evaluation', 'scripts'))
os.environ.setdefault('TESSERAE_USE_DIRECT_SEARCH', '1')
from backend import fusion  # noqa
fusion._SYNTAX_DB_PATH = a.db_la
fusion._SYNTAX_GREEK_DB_PATH = a.db_grc
fusion._SYNTAX_PARSE_CACHE.clear()
from backend.text_processor import TextProcessor  # noqa
from backend.matcher import Matcher  # noqa
from backend.scorer import Scorer  # noqa
from backend.fusion import run_fusion_search  # noqa

tp, matcher, scorer = TextProcessor(), Matcher(), Scorer()
TEXTS = os.path.join(a.root, 'texts')


def search(sf, tf, lang):
    sp, tpth = os.path.join(TEXTS, lang, sf), os.path.join(TEXTS, lang, tf)
    su, tu = tp.process_file(sp, lang, 'line'), tp.process_file(tpth, lang, 'line')
    t0 = time.time()
    res = run_fusion_search(su, tu, matcher, scorer, sf, tf, language=lang, mode='merged', max_results=0,
                            source_path=sp, target_path=tpth)
    return res, time.time() - t0, su, tu


def slim(r, rank):
    s, t = r.get('source', {}), r.get('target', {})
    return {'rank': rank, 'src': s.get('ref', ''), 'tgt': t.get('ref', ''), 'score': r.get('fused_score', 0),
            'channels': r.get('channel_count', 0), 'src_text': s.get('text', ''), 'tgt_text': t.get('text', ''),
            'names': r.get('channels') or r.get('channel_names') or None}


out = {'label': a.label, 'db_la': a.db_la, 'db_grc': a.db_grc}
if a.greek_bench:
    import benchmark_apollonius_homer as bh  # noqa  (its helpers only; main() is not run)
    gold_all = bh.load_benchmark(min_type=4)
    by_src = defaultdict(list)
    for g in gold_all:
        by_src[g['source_file']].append(g)
    tf = 'apollonius_rhodius.argonautica.part.3.tess'
    tu = tp.process_file(os.path.join(TEXTS, 'grc', tf), 'grc', 'line')
    ks = [10, 50, 100, 200]
    found = {k: 0 for k in ks}
    total = 0
    secs = 0.0
    per = {}
    for sf in sorted(by_src):
        sp = os.path.join(TEXTS, 'grc', sf)
        su = tp.process_file(sp, 'grc', 'line')
        t0 = time.time()
        res = run_fusion_search(su, tu, matcher, scorer, sf, tf, language='grc', mode='merged', max_results=0,
                                source_path=sp, target_path=os.path.join(TEXTS, 'grc', tf))
        secs += time.time() - t0
        s_idx = {}
        for i, u in enumerate(su):
            p = bh.normalize_ref(u.get('ref', ''))
            if p:
                s_idx[p] = i
        by_line = defaultdict(list)
        for r in res:
            by_line[r.get('source', {}).get('ref', '')].append(r)
        bf = {k: 0 for k in ks}
        for gp in by_src[sf]:
            total += 1
            gs, gt = bh.normalize_ref(gp['source_ref']), bh.normalize_ref(gp['target_ref'])
            if gs is None or gt is None:
                continue
            idx = s_idx.get(gs)
            if idx is None:
                for d in (-1, 0, 1):
                    if (gs[0], gs[1] + d) in s_idx:
                        idx = s_idx[(gs[0], gs[1] + d)]
                        break
            if idx is None:
                continue
            lr = sorted(by_line.get(su[idx].get('ref', ''), []), key=lambda r: r.get('fused_score', 0), reverse=True)
            rank = None
            for n, r in enumerate(lr, 1):
                tp_ = bh.normalize_ref(r.get('target', {}).get('ref', ''))
                if tp_ and tp_[0] == gt[0] and abs(tp_[1] - gt[1]) <= 3:
                    rank = n
                    break
            if rank:
                for k in ks:
                    if rank <= k:
                        bf[k] += 1
                        found[k] += 1
        per[sf] = {'gold': len(by_src[sf]), 'found': bf}
        print(sf, len(by_src[sf]), bf, flush=True)
    out.update({'greek_bench': True, 'gold': total, 'found_at': found, 'fusion_seconds': secs, 'per_book': per})
else:
    res, secs, su, tu = search(a.source, a.target, a.lang)
    out.update({'source': a.source, 'target': a.target, 'fusion_seconds': secs, 'n_results': len(res),
                'source_lines': len(su), 'target_lines': len(tu)})
    res = sorted(res, key=lambda r: r.get('fused_score', 0), reverse=True)
    if a.gold:
        import benchmark_production_fusion as bp  # noqa
        gold = bp.load_gold(a.gold)
        ev = bp.evaluate_results(res, gold, k_values=[10, 50, 100, 500])
        out['gold_entries'] = ev['total_gold']
        out['found_at'] = {str(k): v for k, v in ev['recall_at_k'].items()}
        out['recall_total'] = ev['total_found']
    out['top'] = [slim(r, i) for i, r in enumerate(res[:a.keep], 1)]
json.dump(out, open(a.out, 'w'), ensure_ascii=False)
print(json.dumps({k: v for k, v in out.items() if k not in ('top', 'per_book')}))
