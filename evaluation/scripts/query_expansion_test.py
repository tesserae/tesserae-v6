"""Does template expansion fix the noun-phrase problem, and what does it cost?

THE PROBLEM, MEASURED

The index is built from SENTENCES describing what happens in a passage, so it
answers sentences. A noun phrase lands somewhere else entirely:

    "warrior arming scene"                    Iliad 19.361 at rank 1440, 0 arming
                                              scenes in the top 50
    "a warrior arms himself before battle"    rank 66, 7 in the top 50
    "the shortness of life"                   best Seneca De Brevitate rank 31
    "life is short"                           rank 1

This is the cheap half of the comparison NC asked for: templates in code, no
model call. The other half asks the local model for paraphrases.

WHAT MUST BE MEASURED, not just recall

Expansion can only make a query match MORE things, so a gain on known targets is
worthless without the cost on the absent probes. Both are reported here. A
version that finds Seneca and also finds airplanes is not an improvement.
"""
import json
import os
import sys

import numpy as np

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT)

from backend import passage_index as pi  # noqa: E402

# Turn whatever was typed into things shaped like a description. Deliberately
# dumb: no parsing, no model, no vocabulary. If this is enough, it is the right
# answer, because it costs nothing and cannot fail at runtime.
TEMPLATES = [
    '{q}',
    'a passage in which {q}',
    'someone describes {q}',
    'this passage is about {q}',
]


def looks_like_a_sentence(q):
    """Rough: a sentence usually has a subject and a verb, and is longer."""
    words = q.split()
    if len(words) < 4:
        return False
    return bool({'is', 'are', 'was', 'were', 'has', 'have', 'and', 'who', 'to',
                 'his', 'her', 'their', 'a', 'an', 'the'} & {w.lower() for w in words[1:]})


def expand(q):
    return [t.format(q=q) for t in TEMPLATES]


def scores_for(texts, combine='max'):
    mats = []
    for t in texts:
        v = pi.embed_query(pi._E5_PREFIX + t)
        mats.append(pi._mask_undescribed(pi._score_all(v)))
    m = np.vstack(mats)
    return m.max(axis=0) if combine == 'max' else m.mean(axis=0)


def ranks_of(scores, rows, cap=20000):
    order = np.argsort(-scores)
    rank = {int(r): n for n, r in enumerate(order[:cap])}
    return [rank.get(i, cap) for i in rows]


def main():
    pi._ensure_loaded()
    import re

    arming = [i for i, r in enumerate(pi._records)
              if str(r.get('ref_start') or '').startswith('hom. il.')
              and re.search(r'\barm(s|ing|ed|our|or)\b',
                            str((r.get('desc') or {}).get('gist') or ''), re.I)]
    seneca = [i for i, r in enumerate(pi._records)
              if 'seneca.de_brevitate_vitae' in str(r.get('work') or '')]
    print(f'targets: {len(arming)} Iliad arming windows, {len(seneca)} Seneca windows\n')

    CASES = [('warrior arming scene', arming), ('the shortness of life', seneca)]

    print(f'{"query":34s} {"mode":9s} {"best":>6s} {"top50":>6s}')
    for q, rows in CASES:
        for mode in ('plain', 'expand-max', 'expand-mean'):
            if mode == 'plain':
                sc = scores_for([q])
            else:
                sc = scores_for(expand(q), 'max' if mode.endswith('max') else 'mean')
            rk = ranks_of(sc, rows)
            print(f'  {q[:32]:32s} {mode:9s} {min(rk):6d} {sum(1 for r in rk if r < 50):6d}')

    # THE COST. Absent subjects must not start looking present.
    print('\nabsent probes (a "low" verdict is correct for all of these):')
    probes = json.load(open(os.path.join(PROJECT, 'evaluation', 'probe_sets',
                                         'tesserae_2026-08.json'), encoding='utf-8'))
    absent = [p['query'] for p in probes if not p['present']][:10]
    worse = 0
    for q in absent:
        base = pi._confidence_level(*head_and_coh(scores_for([q])))
        exp = pi._confidence_level(*head_and_coh(scores_for(expand(q))))
        flag = ''
        if base == 'low' and exp != 'low':
            worse += 1
            flag = '  <-- became findable, which is wrong'
        print(f'  {q[:44]:46s} {base:9s} -> {exp:9s}{flag}')
    print(f'\nabsent subjects that expansion made look present: {worse} of {len(absent)}')


def head_and_coh(scores):
    med = float(np.median(scores))
    k = min(10, len(scores))
    head = float(np.sort(scores)[-k:].mean()) - med
    return head, pi._cluster_coherence(scores)


if __name__ == '__main__':
    main()
