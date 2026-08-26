"""Find a confidence statistic that works at any query length.

THE PROBLEM

Raw similarity scales with query length, so the top-hit lift over the corpus
median is not comparable between a keyword and a sentence. Measured on the live
index:

    "plague"      lift 0.093   -> reads LOW    (top hit IS a plague, Silius 14.581)
    "airplanes"   lift 0.095   -> reads STRONG (top hit is nothing of the kind)

"airplanes" outscores "plague". Every probe the thresholds were fitted on is a
full sentence, so the calibration never covered this case at all.

WHAT THIS TESTS

Several length-independent alternatives, over short queries whose answer is known:

    lift        top - median                    the current measure
    z           (top - mean) / stdev            lift in units of the corpus spread
    z_med       (top - median) / MAD            the same, robust to a skewed tail
    ratio       top / median
    head        mean(top 10) - median           is there a GROUP, not one stray
    coherence   agreement among the top 20      the existing second signal

A statistic worth adopting has to separate present from absent AT EVERY LENGTH,
using one threshold. Anything needing a different cut per length is just the
current problem with more steps.
"""
import json
import os
import statistics
import sys

import numpy as np

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT)

from backend import passage_index as pi  # noqa: E402

# Subjects the corpus certainly holds, and things it certainly does not, at
# one word, two or three words, and full description length.
PROBES = [
    # ---- single words, PRESENT
    ('plague', True), ('shipwreck', True), ('banquet', True), ('prophecy', True),
    ('exile', True), ('sacrifice', True), ('chariot', True), ('siege', True),
    # ---- single words, ABSENT
    ('airplanes', False), ('locomotive', False), ('telegraph', False),
    ('antibiotics', False), ('spacecraft', False), ('photograph', False),
    ('submarine', False), ('television', False),
    # ---- short phrases, PRESENT
    ('a plague', True), ('funeral games', True), ('a storm at sea', True),
    ('the underworld', True),
    # ---- short phrases, ABSENT
    ('airplanes and locomotives', False), ('a steam engine', False),
    ('a printing press', False), ('a vaccine trial', False),
    # ---- descriptions, PRESENT
    ('a plague strikes a city and the dead go unburied', True),
    ('a warrior arms himself before battle, piece by piece', True),
    # ---- descriptions, ABSENT
    ('a photographer develops a glass plate in a darkroom', False),
    ('a compositor sets metal type line by line', False),
]


def stats_for(query):
    pi._ensure_loaded()
    q = pi.embed_query(pi._E5_PREFIX + query.strip()[:1500])
    scores = pi._score_all(q)
    med = float(np.median(scores))
    mean = float(scores.mean())
    sd = float(scores.std()) or 1e-9
    mad = float(np.median(np.abs(scores - med))) or 1e-9
    top = float(scores.max())
    k = min(10, len(scores))
    head = float(np.sort(scores)[-k:].mean())
    return {
        'lift': top - med,
        'z': (top - mean) / sd,
        'z_med': (top - med) / mad,
        'ratio': top / med if med else 0.0,
        'head': head - med,
        'head_z': (head - mean) / sd,
        'coherence': pi._cluster_coherence(scores),
    }


def separation(rows, key):
    """How cleanly one statistic splits present from absent, over ALL lengths."""
    pres = sorted(r[key] for r in rows if r['present'])
    absent = sorted(r[key] for r in rows if not r['present'])
    if not pres or not absent:
        return None
    # best single threshold, and the accuracy it gives
    cands = sorted(set(pres + absent))
    best, best_acc = None, -1.0
    for i in range(len(cands) - 1):
        t = (cands[i] + cands[i + 1]) / 2
        acc = sum(1 for r in rows if (r[key] >= t) == r['present']) / len(rows)
        if acc > best_acc:
            best, best_acc = t, acc
    return {'threshold': best, 'accuracy': best_acc,
            'present_min': min(pres), 'absent_max': max(absent),
            'gap': min(pres) - max(absent)}


def main():
    rows = []
    print(f'{"query":52s} {"n":>2s} {"lift":>7s} {"z":>7s} {"z_med":>7s} '
          f'{"head":>7s} {"head_z":>7s} {"coher":>6s}')
    for query, present in PROBES:
        s = stats_for(query)
        s.update({'query': query, 'present': present, 'words': len(query.split())})
        rows.append(s)
        tag = 'Y' if present else 'n'
        print(f'[{tag}] {query[:48]:48s} {s["words"]:2d} {s["lift"]:7.3f} '
              f'{s["z"]:7.2f} {s["z_med"]:7.2f} {s["head"]:7.3f} '
              f'{s["head_z"]:7.2f} {s["coherence"]:6.3f}')

    print('\nSEPARATION over all lengths (one threshold for every query):')
    for key in ('lift', 'z', 'z_med', 'head', 'head_z', 'ratio', 'coherence'):
        r = separation(rows, key)
        flag = '  <-- clean' if r['gap'] > 0 else ''
        print(f'  {key:10s} accuracy {r["accuracy"]:.0%}  threshold {r["threshold"]:8.3f}  '
              f'present>={r["present_min"]:7.3f}  absent<={r["absent_max"]:7.3f}{flag}')

    out = os.path.join(PROJECT, 'evaluation', 'probe_sets', 'short_query_stats.json')
    json.dump(rows, open(out, 'w'), indent=1)
    print(f'\nwritten: {out}')


if __name__ == '__main__':
    main()
