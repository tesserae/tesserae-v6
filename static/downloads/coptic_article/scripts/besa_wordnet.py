"""Besa's Letters against the Sahidic Psalms on the deployed Tesserae V6 code:
how often the dictionary channel (the Coptic Wordnet synonym pairs) fires in
5,000 ranked results, and how many of the 5,000 pairs change when that channel
is turned off (article §5). The first run of this comparison, on 2026-05-14,
used code that was never saved; this script repeats it on a current checkout.

Run from the root of a Tesserae V6 checkout that holds the Coptic corpus:

    venv/bin/python -I data_release/scripts/besa_wordnet.py [--out DIR]

Four files are written to DIR (default: the outputs folder beside this
script's folder):

  besa_wordnet_2026-11-11.json
      the summary: channel firing counts in the 5,000 and in the top 100 for
      the default Coptic weight profile (biblical_coptic), the same with the
      dictionary channel off, the dictionary firings by rank band, the pairs
      present only with the channel on (first 50 listed with their channels),
      the overlap of the top 20 and top 100, and the same measures under the
      latin_epic profile, whose weights are the defaults the 2026-05-14 run used.
  besa_psalms_ranked_2026-11-11.json
      the 5,000 ranked pairs under biblical_coptic: [Besa line reference,
      Psalm verse reference, channels that fired, fused score].
  besa_psalms_ranked_2026-11-11_no_dictionary.json
      the same with the dictionary channel off.
  besa_psalms_ranked_2026-11-11_latin_epic_weights.json
      the same under the latin_epic profile with every channel on.

Only line references, channel names and scores are written; no text.
"""
import os, sys, json, collections, inspect, time, argparse
sys.path.insert(0, os.getcwd())
from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.fusion import iter_fusion_search, get_channels_for_language

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('--out', default=os.path.join(os.path.dirname(HERE), 'outputs'))
ap.add_argument('--max-results', type=int, default=5000)
a = ap.parse_args()
OUT = a.out
os.makedirs(OUT, exist_ok=True)
TAG = '2026-11-11'

SRC, TGT = 'besa.letters.tess', 'sahidic.psalms.tess'
sp, tp_ = f'texts/cop/{SRC}', f'texts/cop/{TGT}'
tp = TextProcessor()
src = tp.process_file(sp, language='cop')
tgt = tp.process_file(tp_, language='cop')
params = inspect.signature(iter_fusion_search).parameters

def run(enabled=None, profile=None):
    kw = dict(source_units=src, target_units=tgt, matcher=Matcher(), scorer=Scorer(),
              source_id=SRC, target_id=TGT, language='cop', mode='merged',
              max_results=a.max_results, source_path=sp, target_path=tp_)
    if enabled is not None:
        kw['enabled_channels'] = enabled
    if profile and 'user_settings' in params:
        kw['user_settings'] = {'weights_profile': profile}
    t0 = time.time(); results = []
    for evt, data in iter_fusion_search(**kw):
        if evt == 'complete':
            results = data.get('results', [])
    ref = lambda x: x.get('ref') if isinstance(x, dict) else x
    rows = [(ref(r.get('source')), ref(r.get('target')), sorted(r.get('channels') or []),
             round(r.get('fused_score') or 0, 4)) for r in results]
    return rows, round(time.time() - t0, 1)

def firing(rows):
    c = collections.Counter(); c100 = collections.Counter()
    for i, (_, _, ch, _) in enumerate(rows):
        for x in ch:
            c[x] += 1
            if i < 100: c100[x] += 1
    return {k: [c[k], c100[k]] for k in sorted(c)}

def pairs(rows): return [(s, t) for s, t, _, _ in rows]

avail = get_channels_for_language('cop')
no_dict = [c for c in avail if c != 'dictionary']
out = {'source': SRC, 'target': TGT, 'max_results': a.max_results,
       'available_channels': avail, 'n_source_lines': len(src), 'n_target_lines': len(tgt)}

A, tA = run()
B, tB = run(enabled=no_dict)
out['default_profile'] = {'seconds': tA, 'n_results': len(A), 'firing_all_and_top100': firing(A)}
out['dictionary_off'] = {'seconds': tB, 'n_results': len(B), 'firing_all_and_top100': firing(B)}
pa, pb = pairs(A), pairs(B)
sa, sb = set(pa), set(pb)
dict_rows = [(i + 1, s, t) for i, (s, t, ch, _) in enumerate(A) if 'dictionary' in ch]
out['dictionary_firing'] = {
    'count': len(dict_rows),
    'by_rank': {'1-100': sum(1 for r in dict_rows if r[0] <= 100),
                '101-500': sum(1 for r in dict_rows if 100 < r[0] <= 500),
                '501+': sum(1 for r in dict_rows if r[0] > 500)},
    'also_present_with_dictionary_off': sum(1 for _, s, t in dict_rows if (s, t) in sb),
}
only_a = [(i + 1, s, t, ch) for i, (s, t, ch, _) in enumerate(A) if (s, t) not in sb]
out['pairs_only_with_dictionary_on'] = {'count': len(only_a), 'rows': only_a[:50]}
out['pairs_only_with_dictionary_off'] = len(sb - sa)
out['top100_same_set'] = len(set(pa[:100]) & set(pb[:100]))
out['top20_same_set'] = len(set(pa[:20]) & set(pb[:20]))

if 'user_settings' in params:
    C, tC = run(profile='latin_epic')
    out['latin_epic_profile_as_in_may'] = {'seconds': tC, 'n_results': len(C), 'firing_all_and_top100': firing(C)}
    D, tD = run(enabled=no_dict, profile='latin_epic')
    sd = set(pairs(D))
    dc = [(i + 1, s, t) for i, (s, t, ch, _) in enumerate(C) if 'dictionary' in ch]
    out['latin_epic_profile_as_in_may']['dictionary_firing'] = len(dc)
    out['latin_epic_profile_as_in_may']['pairs_only_with_dictionary_on'] = sum(1 for s, t, _, _ in C if (s, t) not in sd)
    out['latin_epic_profile_as_in_may']['dictionary_rows_also_present_off'] = sum(1 for _, s, t in dc if (s, t) in sd)
    json.dump([list(x) for x in C], open(os.path.join(OUT, f'besa_psalms_ranked_{TAG}_latin_epic_weights.json'), 'w'))

json.dump([list(x) for x in A], open(os.path.join(OUT, f'besa_psalms_ranked_{TAG}.json'), 'w'))
json.dump([list(x) for x in B], open(os.path.join(OUT, f'besa_psalms_ranked_{TAG}_no_dictionary.json'), 'w'))
json.dump(out, open(os.path.join(OUT, f'besa_wordnet_{TAG}.json'), 'w'), indent=1)
print(json.dumps({k: out[k] for k in ('dictionary_firing', 'pairs_only_with_dictionary_off', 'top100_same_set', 'top20_same_set')}, indent=1))
