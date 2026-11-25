"""Table 1 baseline rerun with the scoring diagnostics kept (2026-11-24).

Usage: baseline_rerun_diag.py CHECKOUT LANGUAGE SRC_ID TGT_ID GOLD_CSV OUT_JSON
Runs SRC x TGT with the May 2026 baseline weights (today's latin_epic profile with
the quotation and form channels at 0), 5,000 results kept as in May, and records
for every scored pair the rarity multiplier, geometric-mean IDF, number of shared
content words, channels and non-quotation weighted sum (one JSONL row per pair),
then joins those with the ranked list for the top 50 and for the 124 benchmark
pairs (votes >= 20). The two fusion functions are re-executed from their own
source with recording lines added, as in scripts/greek_two_pairs_latin_epic.py.
CHECKOUT is the root of a Tesserae V6 checkout that holds the texts; LANGUAGE is
cop or grc; SRC_ID and TGT_ID are text file stems (sahidica.hebrews, sahidic.psalms;
novum_testamentum.ad_hebraeos, septuaginta.psalmi); GOLD_CSV is
gold/tsk_hebrews_psalms_gold_124.csv. Produced the two baseline rerun files of
2026-11-24 in outputs/. Beside OUT_JSON it writes <stem>_diag.jsonl, one row per
scored pair (about 200,000 rows, not part of the release).
"""
import os, sys, json, time, re, inspect, subprocess, csv
CHECKOUT, LANG, SRC_ID, TGT_ID, GOLD, OUT = sys.argv[1:7]
sys.path.insert(0, CHECKOUT); os.chdir(CHECKOUT)
from dotenv import load_dotenv; load_dotenv(os.path.join(CHECKOUT, '.env'))
import backend.fusion as F
from backend.fusion import iter_fusion_search
from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer

src = inspect.getsource(F._pair_table)
needle = '            entry["score"] += contribution\n'
assert src.count(needle) == 1
src = src.replace(needle, needle +
    '            entry.setdefault("_per_ch_w", {})\n'
    '            entry["_per_ch_w"][ch_name] = entry["_per_ch_w"].get(ch_name, 0.0) + contribution\n')
exec(compile(src, '<patched _pair_table>', 'exec'), F.__dict__)
src = inspect.getsource(F._score_pairs)
needle = '        info["score"] = (\n            non_quotation_base'
assert src.count(needle) == 1
src = src.replace(needle,
    '        _DIAG_WRITE(key, dict(mult=multiplier, geom_idf=geom_mean_idf, base=base_score, quot=quot_contrib, conv=conv_score,\n'
    '            n_unique=n_unique_words, n_content=n_content_words, per_ch_w=info.get("_per_ch_w"), channels=info.get("channels")))\n'
    + needle)
exec(compile(src, '<patched _score_pairs>', 'exec'), F.__dict__)

DIAG_PATH = OUT.replace('.json', '_diag.jsonl')
open(DIAG_PATH, 'w').close()
def _write(key, d):
    s, t = key
    if '-' in str(s).split()[-1] or '-' in str(t).split()[-1]:
        return  # two-line windows are not Table 1 units
    d['key'] = [s, t]
    with open(DIAG_PATH, 'a') as fh:
        fh.write(json.dumps(d, ensure_ascii=False) + '\n')
F._DIAG_WRITE = _write

weights = dict(F.WEIGHT_PROFILES['latin_epic']); weights['quotation'] = 0.0; weights['form'] = 0.0
print('weights', weights, flush=True)
code = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
sub = 'cop' if LANG == 'cop' else 'grc'
src_path = f'texts/{sub}/{SRC_ID}'; tgt_path = f'texts/{sub}/{TGT_ID}'
tp = TextProcessor(); su = tp.process_file(src_path, language=LANG); tu = tp.process_file(tgt_path, language=LANG)
print('units', len(su), len(tu), flush=True)

def cv(ref):
    m = re.search(r'(\d+)\.(\d+)\s*$', ref or '')
    return (m.group(1), m.group(2)) if m else None
gold = []
for r in csv.DictReader(open(GOLD)):
    try: v = int(r['votes'])
    except ValueError: v = 0
    if v >= 20:
        gold.append((cv(r['nt_v6_ref']), cv(r['lxx_v6_ref']), v))
gold_keys = {(a, b) for a, b, _ in gold}
print('gold pairs', len(gold), flush=True)

t0 = time.time(); final = []
for evt, data in iter_fusion_search(source_units=su, target_units=tu, matcher=Matcher(), scorer=Scorer(),
        source_id=SRC_ID, target_id=TGT_ID, language=LANG, mode='merged', max_results=5000,
        source_path=src_path, target_path=tgt_path, channel_weights=weights):
    if evt == 'complete': final = data.get('results', [])
elapsed = round(time.time() - t0)
print('results', len(final), 'elapsed', elapsed, flush=True)

diag = {}
for line in open(DIAG_PATH):
    d = json.loads(line); diag[(cv(d['key'][0]), cv(d['key'][1]))] = d
print('diag rows', len(diag), flush=True)

rows = []
seen = set()
for i, r in enumerate(final, 1):
    s = r.get('source', {}).get('ref', ''); t = r.get('target', {}).get('ref', '')
    if r.get('is_window') or '-' in s.split()[-1] or '-' in t.split()[-1]:
        continue
    k = (cv(s), cv(t))
    d = diag.get(k, {})
    rows.append({'rank': i, 'source': s, 'target': t, 'gold': k in gold_keys, 'score': r.get('fused_score'),
                 'channels': r.get('channels'), 'mult': d.get('mult'), 'geom_idf': d.get('geom_idf'),
                 'n_content': d.get('n_content'), 'per_ch_w': d.get('per_ch_w'), 'base': d.get('base'), 'conv': d.get('conv')})
gold_ranks = {}
for row in rows:
    k = (cv(row['source']), cv(row['target']))
    if row['gold'] and k not in gold_ranks:
        gold_ranks[k] = row['rank']
recall = {n: sum(1 for k in gold_keys if gold_ranks.get(k, 10**9) <= n) for n in (50, 100, 500, 1000, 5000)}
print('recall', recall, flush=True)
out = {'date': time.strftime('%Y-%m-%d %H:%M:%S %Z'), 'code': code, 'language': LANG, 'source': SRC_ID, 'target': TGT_ID,
       'weights': weights, 'max_results': 5000, 'n_results': len(final), 'elapsed_s': elapsed, 'n_gold': len(gold),
       'recall': recall,
       'gold_pairs': [{'nt': a, 'lxx': b, 'votes': v, 'rank': gold_ranks.get((a, b)),
                       'diag': {kk: vv for kk, vv in diag.get((a, b), {}).items() if kk != 'key'}} for a, b, v in gold],
       'top50': rows[:50] if len(rows) >= 50 else rows,
       'top100_rows': [r for r in rows if r['rank'] <= 100]}
json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
print('DONE', flush=True)
