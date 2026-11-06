"""The closing merge of a large comparison gives the answers it always gave (2026-10-27)."""
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import fusion  # noqa: E402


def _legacy_dedup(window_results):
    """The overlap removal as it was before the cell table (the specification)."""
    if not window_results:
        return window_results
    parsed = []
    for r in window_results:
        rs = r.get("source", {}).get("ref", "")
        rt = r.get("target", {}).get("ref", "")
        sb, ss, se = fusion.parse_range_ref(rs)
        tb, ts, te = fusion.parse_range_ref(rt)
        parsed.append((sb, ss, se, tb, ts, te))
    word_sets = []
    for r in window_results:
        word_sets.append(frozenset(mw.get("lemma", "") for mw in r.get("matched_words", [])
                                   if mw.get("lemma")))
    scored = sorted(range(len(window_results)),
                    key=lambda i: window_results[i].get('fused_score', 0), reverse=True)
    kept = []
    kept_by_tgt_line = defaultdict(list)
    for i in scored:
        sb, ss, se, tb, ts, te = parsed[i]
        if sb is None or tb is None:
            kept.append(window_results[i])
            continue
        is_dup = False
        cand_lemmas = word_sets[i]
        checked = set()
        for tl in range(ts, te + 1):
            for entry in kept_by_tgt_line.get((tb, tl), []):
                eid = id(entry)
                if eid in checked:
                    continue
                checked.add(eid)
                ksb, kss, kse, _, kts, kte, k_lemmas = entry
                if sb != ksb:
                    continue
                if ss <= kse and kss <= se:
                    if not cand_lemmas or cand_lemmas <= k_lemmas:
                        is_dup = True
                        break
            if is_dup:
                break
        if not is_dup:
            kept.append(window_results[i])
            entry = (sb, ss, se, tb, ts, te, cand_lemmas)
            for tl in range(ts, te + 1):
                kept_by_tgt_line[(tb, tl)].append(entry)
    return kept


def _row(rng, n, irregular):
    def ref():
        book = rng.randint(1, 3)
        line = rng.randint(1, 14)
        roll = rng.random()
        if roll < 0.04:
            return 'x'                                    # no coordinates
        if irregular and roll < 0.12:
            return f'w {book}.{line + rng.randint(1, 30)}-w {book}.{line}'     # reversed
        if irregular and roll < 0.2:
            return f'w {book}.{line}-w {book}.{line + rng.randint(5, 40)}'     # wide
        if roll < 0.25:
            return f'w {book}.{line}-w {book + 1}.{line}'                      # across books
        if roll < 0.35:
            return f'w {book}.{line}'                                          # one line
        return f'w {book}.{line}-w {book}.{line + 1}'
    lemmas = rng.sample(['a', 'b', 'c', 'd', 'e', ''], rng.randint(0, 3))
    return {'source': {'ref': ref()}, 'target': {'ref': ref()},
            'fused_score': round(rng.random() * 3, 1) if rng.random() < 0.7 else float(n),
            'matched_words': [{'lemma': x} for x in lemmas], 'n': n}


def test_dedup_keeps_exactly_the_windows_it_always_kept():
    rng = random.Random(1027)
    for trial in range(60):
        rows = [_row(rng, n, irregular=(trial % 2 == 1)) for n in range(rng.randint(1, 400))]
        got = fusion._dedup_overlapping_windows(list(rows))
        want = _legacy_dedup(list(rows))
        assert [r['n'] for r in got] == [r['n'] for r in want], trial


def test_lowered_word_indices_match_the_original():
    rng = random.Random(5)
    words = ['Arma', 'virum', 'CANO', 'cano', 'Troiae', '', 'Ωκεανός', 'ὠκεανός']
    for _ in range(300):
        tokens = [rng.choice(words) for _ in range(rng.randint(0, 6))]
        word = rng.choice(words + [None])
        lowered = [t.lower() for t in tokens]
        assert fusion._lowered_word_indices(lowered, word) == fusion._matched_word_indices(tokens, word)
