#!/usr/bin/env python3
"""Propose additions to hebrew_greek.csv from the corpus's own verse alignment
(issue #519), WITHOUT hand-editing the dictionary from outside knowledge.

For each of the 200 most frequent Hebrew lemmas (by raw token count across the
whole Hebrew Bible), finds Greek lemmas that co-occur with it in the
Septuagint's aligned verses far more often than chance, and writes every
(hebrew, greek) pair not already in hebrew_greek.csv to a proposals CSV for a
human to review and merge. Nothing here touches the dictionary itself.

ALIGNMENT: book map and versification come from backend/lxx_pivot.py (the
same table the Septuagint pivot route uses), restricted to books with both a
Hebrew text and a routed Septuagint counterpart. Jeremiah, Ezra, Nehemiah,
Ecclesiastes, and Lamentations are excluded there for the same reasons the
pivot excludes them (see lxx_pivot.EXCLUDED); their Hebrew lemmas still count
toward the frequency ranking (computed over the WHOLE Hebrew Bible), but have
no co-occurrence evidence to propose from.

STATISTIC: for a pair (he, grc), let
  cooccur(he, grc)   = number of aligned verses containing both lemmas
  doc_freq(he)       = number of aligned verses containing he
  doc_freq(grc)      = number of aligned verses containing grc
  N                  = total aligned verses
ratio = [cooccur(he, grc) / doc_freq(he)] / [doc_freq(grc) / N]
      = cooccur(he, grc) * N / (doc_freq(he) * doc_freq(grc))
i.e. how many times more often grc appears in a verse that also has he than
grc's own base rate would predict (document frequency, not raw token counts,
so a verse that repeats a common Greek word several times doesn't inflate its
own base rate). A real translation equivalent should co-occur far above
chance; MIN_RATIO and MIN_COOCCUR below set "far above chance" and "enough
evidence to trust it" respectively -- both are starting points for the
reviewer to tighten or loosen, not a precision guarantee.

Hebrew final-letter forms: hebrew_greek.csv (CATSS-derived) writes word-final
kaf/mem/nun/pe/tsade in medial form; the Hebrew lemmatizer (and so this
script's own counts) writes the final form (issue #517). The existing-pairs
set loaded here is normalized to final form so a lemma already covered under
its CATSS spelling is not proposed again as if it were new.
"""
import csv
import glob
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.text_processor import TextProcessor
from backend.hebrew import register as register_hebrew
register_hebrew()
from backend import lxx_pivot

TOP_N_HEBREW = 200
MIN_COOCCUR = 10
MIN_RATIO = 5.0

HEBREW_GREEK_CSV = os.path.join(ROOT, 'backend', 'synonymy', 'v6_additions', 'hebrew_greek.csv')
OUT_PATH = os.path.join(ROOT, 'data', 'proposals', 'hebrew_greek_additions_2026-09-30.csv')

# Mirrors backend/blueprints/search.py:_HEBREW_FINAL_FORMS (issue #517): CATSS
# writes these five letters in medial form word-finally; the lemmatizer (and
# this script) uses the final form.
_HEBREW_MEDIAL_TO_FINAL = dict(zip('כמנפצ', 'ךםןףץ'))


def _to_final_form(word):
    if word and word[-1] in _HEBREW_MEDIAL_TO_FINAL:
        return word[:-1] + _HEBREW_MEDIAL_TO_FINAL[word[-1]]
    return word


def load_existing_pairs():
    pairs = set()
    with open(HEBREW_GREEK_CSV, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',')
            if len(parts) < 2:
                continue
            he = _to_final_form(parts[0].strip())
            grc = parts[1].strip()
            if he and grc:
                pairs.add((he, grc))
    return pairs


def main():
    tp = TextProcessor()
    existing = load_existing_pairs()

    # --- Whole-Hebrew-Bible lemma frequency, for the top-200 ranking ---
    he_freq = Counter()
    he_units_by_book = {}
    he_files = sorted(glob.glob(os.path.join(ROOT, 'texts', 'he', 'hebrew_bible.*.tess')))
    for path in he_files:
        book = os.path.basename(path)[len('hebrew_bible.'):-len('.tess')]
        units = tp.process_file(path, 'he', 'line')
        he_units_by_book[book] = units
        for u in units:
            for lemma in u.get('lemmas', []):
                if lemma:
                    he_freq[lemma] += 1

    # --- Aligned-verse co-occurrence, pooled across every routable book ---
    cooccur = Counter()
    he_doc_freq = Counter()
    grc_doc_freq = Counter()
    total_aligned = 0
    books_used = []
    for book, lxx_stem in sorted(lxx_pivot.BOOKS.items()):
        he_units = he_units_by_book.get(book)
        grc_path = os.path.join(ROOT, 'texts', 'grc', f'septuaginta.{lxx_stem}.tess')
        if he_units is None or not os.path.exists(grc_path):
            continue
        grc_units = tp.process_file(grc_path, 'grc', 'line')

        he_by_verse = defaultdict(set)
        for u in he_units:
            ref = u.get('ref', '')
            if ref:
                he_by_verse[ref].update(l for l in u.get('lemmas', []) if l)

        grc_by_verse = defaultdict(set)
        for u in grc_units:
            heb_ref = lxx_pivot.hebrew_ref_for_lxx_ref(u.get('ref', ''), f'hebrew_bible.{book}', book)
            if heb_ref:
                grc_by_verse[heb_ref].update(l for l in u.get('lemmas', []) if l)

        shared = set(he_by_verse) & set(grc_by_verse)
        if not shared:
            continue
        books_used.append((book, len(shared)))
        for ref in shared:
            total_aligned += 1
            he_lemmas = he_by_verse[ref]
            grc_lemmas = grc_by_verse[ref]
            for hl in he_lemmas:
                he_doc_freq[hl] += 1
            for gl in grc_lemmas:
                grc_doc_freq[gl] += 1
            for hl in he_lemmas:
                for gl in grc_lemmas:
                    cooccur[(hl, gl)] += 1

    # --- Propose, for each of the top-200 Hebrew lemmas, the Greek lemmas it
    # co-occurs with far above chance and does not already have ---
    # Build a he_lemma -> [(grc_lemma, count), ...] index ONCE (a single pass
    # over cooccur) rather than rescanning the whole table per top-200 lemma,
    # which is O(200 * |cooccur|) and was the actual bottleneck (|cooccur| can
    # run into the hundreds of thousands of distinct pairs over the whole
    # aligned Bible).
    by_hebrew = defaultdict(list)
    for (hl, gl), c in cooccur.items():
        by_hebrew[hl].append((gl, c))

    top_hebrew = [he for he, _ in he_freq.most_common(TOP_N_HEBREW)]
    proposals = []  # (hebrew, greek, cooccurrences, ratio), one row per pair
    for rank, he in enumerate(top_hebrew, start=1):
        he_n = he_doc_freq.get(he, 0)
        if he_n == 0:
            continue  # no aligned-verse evidence at all for this lemma
        candidates = by_hebrew.get(he, [])
        for gl, c in candidates:
            if c < MIN_COOCCUR:
                continue
            if (he, gl) in existing:
                continue
            grc_n = grc_doc_freq.get(gl, 0)
            if grc_n == 0:
                continue
            ratio = (c * total_aligned) / (he_n * grc_n)
            if ratio < MIN_RATIO:
                continue
            proposals.append((he, gl, c, ratio, rank))

    # Highest-frequency Hebrew lemma first, then its strongest-evidence pairs.
    proposals.sort(key=lambda row: (row[4], -row[2], -row[3]))

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['hebrew', 'greek', 'cooccurrences', 'ratio'])
        for he, gl, c, ratio, _rank in proposals:
            writer.writerow([he, gl, c, f'{ratio:.2f}'])

    print(f"Aligned books used: {books_used}")
    print(f"Total aligned verses: {total_aligned}")
    print(f"Top-{TOP_N_HEBREW} Hebrew lemmas by frequency: {len(top_hebrew)}")
    print(f"Proposed new pairs (cooccur>={MIN_COOCCUR}, ratio>={MIN_RATIO}): {len(proposals)}")
    print(f"Wrote {OUT_PATH}")
    print("\nFirst 30 proposals:")
    for he, gl, c, ratio, rank in proposals[:30]:
        print(f"  [{rank:>3}] {he} -> {gl}  (cooccur={c}, ratio={ratio:.1f})")


if __name__ == '__main__':
    main()
