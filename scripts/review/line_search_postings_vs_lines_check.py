#!/usr/bin/env python3
"""Check that, for the very common lemmas, an index's `lines` table says what its `postings` table says.

The rarest-first lemma lookup (backend/inverted_index.py, _lookup_rarest_first)
finds a very common lemma on a candidate line by reading that line's row of
`lines` instead of the lemma's posting list. That is the same answer only while
the two tables agree. This script compares them: for every lemma with at least
COMMON_LEMMA_POSTINGS postings, in every text whose line_count equals its rows
in `lines` (the texts the lookup reads from `lines`), the (ref, positions) pairs
of the postings must equal those derived from `lines.lemmas`. Run it after any
edit to an index that touches `lines` or `postings`.

    ~/bin/tess-job --fg lscheck 6 PY scripts/review/line_search_postings_vs_lines_check.py la grc

Exit status 1 on any difference.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend import inverted_index as II  # noqa: E402


def check(language):
    path = os.path.join(II.INDEX_DIR, f'{language}_index.db')
    conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    common = [r[0] for r in conn.execute(
        'SELECT lemma FROM postings GROUP BY lemma HAVING COUNT(*) >= ?', (II.COMMON_LEMMA_POSTINGS,))]
    print(f'{language}: {len(common)} lemmas with at least {II.COMMON_LEMMA_POSTINGS} postings', flush=True)
    texts = {t: (lc, rows) for t, lc, rows in conn.execute(
        'SELECT t.text_id, t.line_count, (SELECT COUNT(*) FROM lines l WHERE l.text_id = t.text_id) FROM texts t')}
    clean = {t for t, (lc, rows) in texts.items() if lc == rows}
    print(f'{language}: {len(clean)} of {len(texts)} texts read from `lines`', flush=True)
    bad = 0
    checked = 0
    marks = ','.join('?' for _ in common)
    for text_id in sorted(clean):
        from_postings = {}
        for lemma, ref, positions in conn.execute(
                f'SELECT lemma, ref, positions FROM postings INDEXED BY idx_text WHERE text_id = ? AND lemma IN ({marks})',  # nosec B608
                [text_id] + common):
            from_postings.setdefault((lemma, ref), []).append(json.loads(positions))
        from_lines = {}
        for ref, lemmas_json in conn.execute('SELECT ref, lemmas FROM lines WHERE text_id = ?', (text_id,)):
            lemmas = json.loads(lemmas_json)
            for lemma in set(lemmas) & set(common):
                from_lines[(lemma, ref)] = [[i for i, x in enumerate(lemmas) if x == lemma]]
        checked += len(from_postings)
        if from_postings != from_lines:
            bad += 1
            only_p = set(from_postings) - set(from_lines)
            only_l = set(from_lines) - set(from_postings)
            differing = [k for k in set(from_postings) & set(from_lines) if from_postings[k] != from_lines[k]]
            print(f'  DIFFERENT text_id {text_id}: {len(only_p)} only in postings, {len(only_l)} only in lines, '
                  f'{len(differing)} with other positions', flush=True)
    print(f'{language}: {checked} postings of common lemmas compared, {bad} texts differ', flush=True)
    return bad


if __name__ == '__main__':
    langs = sys.argv[1:] or ['la', 'grc']
    sys.exit(1 if sum(check(lang) for lang in langs) else 0)
