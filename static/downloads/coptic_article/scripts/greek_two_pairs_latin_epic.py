"""Greek Hebrews x Greek Psalms on a Tesserae V6 checkout with the latin_epic weight
profile: the rank, fused score, per-channel scores and rarity multiplier of
Hebrews 13:6 with Psalm 117:6 and with Psalm 117:7 (article, the Table 1 pair).

The search is the one the deployed code runs for a Greek text pair (line matches
plus the two-line window pass, 50,000 results kept). To read the per-channel
scores and the rarity multiplier, the two scoring functions of backend/fusion.py
are re-executed from their own source with recording lines added; the search's
parts run in forked worker processes, so each pair's scoring table is written to
a file from wherever it is scored. The scoring table's last row for each pair
reproduces the fused score listed for it.

Run from the root of a Tesserae V6 checkout that holds the Greek corpus:
    python scripts/greek_two_pairs_latin_epic.py --out outputs/greek_hebrews_psalms_two_pairs_latin_epic_2026-11-12.json
Writes that file and, beside it, <out stem>_scoring_table.jsonl. First run 2026-11-12.
A warning that accepted review entries could not be loaded (no database configured) can be
ignored: those entries belong to the Greek-Latin dictionary, which this search does not use.
"""
import argparse, os, sys, json, time, re, inspect, subprocess
sys.path.insert(0, os.getcwd())
import backend.fusion as F
from backend.fusion import iter_fusion_search
from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer

ap = argparse.ArgumentParser()
ap.add_argument('--out', default='greek_hebrews_psalms_two_pairs_latin_epic.json')
args = ap.parse_args()
OUT = args.out
TABLE = os.path.splitext(OUT)[0] + '_scoring_table.jsonl'

# --- re-execute _pair_table with per-channel raw and weighted scores kept ---
src = inspect.getsource(F._pair_table)
needle = '            entry["score"] += contribution\n'
assert src.count(needle) == 1
src = src.replace(needle, needle +
    '            entry.setdefault("_per_ch", {})\n'
    '            entry["_per_ch"][ch_name] = entry["_per_ch"].get(ch_name, 0.0) + raw_score\n'
    '            entry.setdefault("_per_ch_w", {})\n'
    '            entry["_per_ch_w"][ch_name] = entry["_per_ch_w"].get(ch_name, 0.0) + contribution\n')
exec(compile(src, '<patched _pair_table>', 'exec'), F.__dict__)

# --- re-execute _score_pairs with the multiplier and the assembly terms recorded ---
src = inspect.getsource(F._score_pairs)
needle = '        info["score"] = (\n            non_quotation_base'
assert src.count(needle) == 1
src = src.replace(needle,
    '        info["_diag"] = dict(mult=multiplier, geom_idf=geom_mean_idf, base=base_score,\n'
    '            quot=quot_contrib, conv=conv_score, n_unique=n_unique_words,\n'
    '            n_content=n_content_words, n_scoring=n, penalty_power=_penalty_power,\n'
    '            conv_power=_conv_idf_power, idf_weight=idf_weight, weighted_n=weighted_n)\n'
    '        if _DIAG_WANT(key):\n'
    '            _DIAG_WRITE(key, info)\n'
    + needle)
exec(compile(src, '<patched _score_pairs>', 'exec'), F.__dict__)

open(TABLE, 'w').close()

def _want(key):
    s, t = key
    return s.endswith('13.6') and (t.endswith('117.6') or t.endswith('117.7')) and '-' not in s.split()[-1] and '-' not in t.split()[-1]

def _write(key, info):
    row = {'key': list(key), 'pid': os.getpid(), 'weighted_sum': info.get('score'),
           'per_channel_raw': info.get('_per_ch'), 'per_channel_weighted': info.get('_per_ch_w'),
           'diag': info.get('_diag'), 'channels': info.get('channels'),
           'matched_words': sorted(info.get('all_matched_words', {}).keys())}
    with open(TABLE, 'a') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')

F._DIAG_WANT = _want
F._DIAG_WRITE = _write

weights = dict(F.WEIGHT_PROFILES['latin_epic'])
print('latin_epic weights', weights, flush=True)
try:
    code = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
except Exception:
    code = ''

src_id = 'novum_testamentum.ad_hebraeos.tess'; tgt_id = 'septuaginta.psalmi.tess'
src_path = os.path.join('texts', 'grc', src_id); tgt_path = os.path.join('texts', 'grc', tgt_id)
tp = TextProcessor(); matcher = Matcher(); scorer = Scorer()
su = tp.process_file(src_path, language='grc'); tu = tp.process_file(tgt_path, language='grc')
print('units', len(su), len(tu), flush=True)

def key_of(ref):
    m = re.search(r'(\d+)\.(\d+)\s*$', ref or '')
    return (m.group(1), m.group(2)) if m else None

t0 = time.time(); final = []
for evt, data in iter_fusion_search(source_units=su, target_units=tu, matcher=matcher, scorer=scorer,
        source_id=src_id, target_id=tgt_id, language='grc', mode='merged', max_results=50000,
        source_path=src_path, target_path=tgt_path):  # a Greek pair reads the latin_epic profile
    if evt == 'complete': final = data.get('results', [])
elapsed = round(time.time() - t0)
print('results', len(final), 'elapsed', elapsed, flush=True)

want = {('13', '6'): {('117', '6'): 'Hebrews 13:6 with Psalm 117:6', ('117', '7'): 'Hebrews 13:6 with Psalm 117:7'}}
out = {'date': time.strftime('%Y-%m-%d %H:%M:%S %Z'), 'code': code, 'weights': weights, 'mode': 'merged',
       'max_results': 50000, 'n_results': len(final), 'elapsed_s': elapsed, 'pairs': {}}
for i, r in enumerate(final, 1):
    s = r.get('source', {}).get('ref', ''); t = r.get('target', {}).get('ref', '')
    ks, kt = key_of(s), key_of(t)
    if ks in want and kt in want[ks] and '-' not in s.split()[-1] and '-' not in t.split()[-1]:
        name = want[ks][kt]
        if name in out['pairs']: continue
        out['pairs'][name] = {'rank': i, 'source_ref': s, 'target_ref': t, 'fused_score_listed': r.get('fused_score'),
                              'channels_listed': r.get('channels')}

# The scoring runs again each time a channel finishes, so a pair has several table rows;
# the last row for each pair is the final one. Keep only the final rows.
rows = [json.loads(l) for l in open(TABLE)]
last = {}
for row in rows:
    last[tuple(row['key'])] = row
with open(TABLE, 'w') as fh:
    for row in last.values():
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')
for (s, t), row in last.items():
    ks, kt = key_of(s), key_of(t)
    if ks in want and kt in want[ks]:
        d = out['pairs'].setdefault(want[ks][kt], {'rank': None, 'source_ref': s, 'target_ref': t})
        g = row['diag']
        d['scoring_table'] = row
        d['fused_score_assembled'] = round((g['base'] - g['quot']) * g['mult'] ** g['penalty_power'] + g['quot']
                                           + g['conv'] * g['mult'] ** g['conv_power'], 4)
json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'scoring_table'} for k, v in out['pairs'].items()}, indent=1, ensure_ascii=False), flush=True)
print('wrote', OUT, 'and', TABLE, flush=True)
