"""Sahidic Psalms x Sahidica Hebrews on a Tesserae V6 checkout: the shipped
biblical_coptic weights twice (to measure run-to-run variation) and once with the
semantic weight set to 0 (the ablation of article section 3.4). Compares the three
ranked lists of 10,000 position by position and as sets, and gives the recall of
the 124-pair benchmark and of the 29-pair verbatim list in each run.

Run from the root of a Tesserae V6 checkout that holds the Coptic corpus:
    python scripts/semantic_ablation_lists.py --release-dir . --out outputs/hebrews_psalms_semantic_ablation_2026-11-12.json
--release-dir is the folder holding gold/tsk_hebrews_psalms_gold_124.csv and
gold/hebrews_psalms_verbatim_29.csv (this release). Writes the comparison to --out
and the three ranked lists (reference, reference, fused score) to <out stem>_ranked.json.
No text is written. First run 2026-11-12.
A warning that accepted review entries could not be loaded (no database configured) can be
ignored: those entries belong to the Greek-Latin dictionary, which this search does not use.
"""
import argparse, os, sys, json, csv, time, subprocess
sys.path.insert(0, os.getcwd())
import backend.fusion as F
from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.fusion import iter_fusion_search

ap = argparse.ArgumentParser()
ap.add_argument('--release-dir', default='.')
ap.add_argument('--out', default='hebrews_psalms_semantic_ablation.json')
args = ap.parse_args()
OUT = args.out
R = args.release_dir

src_id, tgt_id = 'sahidic.psalms.tess', 'sahidica.hebrews.tess'
sp, tpth = os.path.join('texts', 'cop', src_id), os.path.join('texts', 'cop', tgt_id)
tp = TextProcessor(); src = tp.process_file(sp, language='cop'); tgt = tp.process_file(tpth, language='cop')
shipped = dict(F.WEIGHT_PROFILES['biblical_coptic'])
ablated = dict(shipped); ablated['semantic'] = 0.0
print('shipped', shipped, flush=True)
try:
    code = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
except Exception:
    code = ''

def run(weights, top=10000):
    # The weights are set on the biblical_coptic profile itself, which the search reads for a
    # Coptic pair. (The channel_weights argument is the web form's path and clamps each weight
    # to at most 20, which would cut the shipped quotation and sound weights.)
    F.WEIGHT_PROFILES['biblical_coptic'].clear(); F.WEIGHT_PROFILES['biblical_coptic'].update(weights)
    t0 = time.time(); results = []
    for evt, data in iter_fusion_search(source_units=src, target_units=tgt, matcher=Matcher(), scorer=Scorer(),
            source_id=src_id, target_id=tgt_id, language='cop', mode='merged', max_results=top,
            source_path=sp, target_path=tpth):
        if evt == 'complete': results = data.get('results', [])
    ref = lambda x: x.get('ref') if isinstance(x, dict) else x
    rows = [(ref(r.get('source')), ref(r.get('target')), round(r.get('fused_score') or 0, 4)) for r in results]
    print('run', len(rows), 'rows', round(time.time() - t0), 's', flush=True)
    return rows

def recall(ranked, gold, depths=(10, 50, 100, 500, 1000, 5000)):
    pos = {(s, t): i + 1 for i, (s, t, _) in enumerate(ranked)}
    return {d: sum(1 for g in gold if pos.get(g, 10**9) <= d) for d in depths}

def compare(a, b):
    pa = [(s, t) for s, t, _ in a]; pb = [(s, t) for s, t, _ in b]
    n = min(len(pa), len(pb))
    same_pos = sum(1 for i in range(n) if pa[i] == pb[i])
    first_diff = next((i + 1 for i in range(n) if pa[i] != pb[i]), None)
    sa, sb = dict(((s, t), sc) for s, t, sc in a), dict(((s, t), sc) for s, t, sc in b)
    common = set(sa) & set(sb)
    score_diff = sum(1 for k in common if abs(sa[k] - sb[k]) > 1e-6)
    max_score_diff = max((abs(sa[k] - sb[k]) for k in common), default=0.0)
    return {'rows': [len(pa), len(pb)], 'same_pair_at_same_position': same_pos, 'first_position_that_differs': first_diff,
            'set_overlap_top': {d: len(set(pa[:d]) & set(pb[:d])) for d in (10, 50, 100, 500, 1000, 5000, 10000)},
            'pairs_in_both': len(common), 'pairs_whose_score_differs': score_diff, 'largest_score_difference': round(max_score_diff, 4)}

g124 = [(r['lxx_v6_ref'], r['nt_v6_ref']) for r in csv.DictReader(open(os.path.join(R, 'gold', 'tsk_hebrews_psalms_gold_124.csv')))]
g29 = [(r['lxx_v6_ref'], r['nt_v6_ref']) for r in csv.DictReader(open(os.path.join(R, 'gold', 'hebrews_psalms_verbatim_29.csv')))]

A = run(shipped); B = run(shipped); C = run(ablated)
F.WEIGHT_PROFILES['biblical_coptic'].clear(); F.WEIGHT_PROFILES['biblical_coptic'].update(shipped)
out = {'date': time.strftime('%Y-%m-%d %H:%M:%S %Z'), 'code': code, 'weights_shipped': shipped, 'weights_ablated': ablated,
       'shipped_vs_shipped': compare(A, B), 'shipped_vs_semantic0': compare(A, C), 'shipped2_vs_semantic0': compare(B, C),
       'recall124': {'shipped_1': recall(A, g124), 'shipped_2': recall(B, g124), 'semantic0': recall(C, g124)},
       'recall29': {'shipped_1': recall(A, g29), 'shipped_2': recall(B, g29), 'semantic0': recall(C, g29)}}
json.dump(out, open(OUT, 'w'), indent=1)
json.dump({'shipped_1': A, 'shipped_2': B, 'semantic0': C}, open(os.path.splitext(OUT)[0] + '_ranked.json', 'w'))
print(json.dumps(out, indent=1), flush=True)
print('wrote', OUT, flush=True)
