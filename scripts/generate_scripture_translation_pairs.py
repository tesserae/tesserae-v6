#!/usr/bin/env python3
"""Regenerate data/translation_pairs.json's scripture pairs, exhaustively.

NC, 2026-09-19: the connections map still showed the World English Bible
against the Hebrew Bible and the Septuagint, and the Bohairic against the
World English Bible, as the DARKEST cells with translation pairs hidden --
because the curated list that hides them only had a handful of sampled
book correspondences (e.g. Hebrew Exodus <-> WEB Pentateuch, but not
Genesis, Leviticus, Numbers or Deuteronomy against that same WEB work),
not the full set. This script generates every one, from
backend/scripture_id.py's own book-name mapping, for every PAIR of the
seven versions in the corpus (Hebrew, Septuagint, Greek New Testament,
Vulgate, Bohairic, Sahidic, World English Bible) -- 21 version pairs, not
just the ones already known to touch one hub version.

Method, per version (a "collection" in scripture_id.py's terms):
  1. List its .tess files under texts/<language>/.
  2. Collapse each to its CONNECTIONS-MAP work id (norm_work: strip any
     ".part.N" segment) -- the same granularity backend/connections_map.py
     and scripts/build_connections_map.py operate at, so a curated pair
     here actually matches a work_pairs row there.
  3. Find which Bible book(s) each ORIGINAL file (before collapsing)
     covers, via scripture_id's own book-name table, from the file's own
     name (a part file's book suffix, e.g. "world_english_bible.pentateuch.
     part.2.exodus" -> EXO; a whole-book file's own name, e.g.
     "hebrew_bible.exodus" -> EXO). A coarse work like
     "world_english_bible.pentateuch" or "jerome.vulgate" ends up mapped to
     every book its OWN part files cover, which is exactly the set of
     books it is a translation of.
  4. For every pair of versions and every book both cover, pair every work
     id of the first covering that book with every work id of the second
     covering it. This is usually one-to-one; it is many-to-one wherever a
     Vulgate/WEB coarse work absorbs several of the other version's
     per-book files (the exact case this script exists to fix), and the
     de-dup step below collapses repeats from multiple shared books in the
     same work pair into one entry.

A book neither scripture_id.py's table nor a file's own name resolves is
skipped silently (aggregate files like "sahidic.bible.tess" have no single
book and are not scripture-paired individually; their sibling per-book
files already cover the same ground).

The one hand-added literary pair (Eobanus/Homer, not scripture at all) is
kept exactly as it was.

Usage:
    python3 scripts/generate_scripture_translation_pairs.py [--write]
Without --write, prints a summary and leaves data/translation_pairs.json
untouched, so the diff can be reviewed first.
"""
import itertools
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend import scripture_id  # noqa: E402

TEXTS_DIR = os.path.join(ROOT, 'texts')
OUT_PATH = os.path.join(ROOT, 'data', 'translation_pairs.json')

# collection key (scripture_id._COLLECTIONS) -> (language dir, file prefix).
# jerome's non-Bible works (epistulae, in_hieremiam_prophetam, ...) are
# excluded by requiring the "vulgate" prefix specifically.
VERSIONS = {
    'hebrew_bible': ('he', 'hebrew_bible.'),
    'septuaginta': ('grc', 'septuaginta.'),
    'novum_testamentum': ('grc', 'novum_testamentum.'),
    'jerome.vulgate': ('la', 'jerome.vulgate'),
    'bohairic': ('cop', 'bohairic.'),
    'sahidic': ('cop', 'sahidic.'),
    'sahidica': ('cop', 'sahidica.'),
    'world_english_bible': ('en', 'world_english_bible.'),
}

HAND_ADDED = [
    {'work_a': 'eobanus.iliad', 'work_b': 'homer.iliad', 'language_a': 'la', 'language_b': 'grc',
     'reason': 'verse paraphrase of Homer (16th c. Latin Iliad)'},
]


def norm_work(work):
    """Same collapse scripts/build_connections_map.py's own norm_work does."""
    w = work or ''
    if w.endswith('.tess'):
        w = w[:-5]
    return w.split('.part.')[0]


def book_of_filename(stem):
    """The book scripture_id.py's table recognises in a bare .tess stem
    (no language dir, no .tess), trying the whole stem and its last
    dot-segment (a part file's own book suffix)."""
    b = scripture_id._book_of(stem)
    if b:
        return b
    return scripture_id._book_of(stem.rsplit('.', 1)[-1])


def collection_books(lang, prefix):
    """coarse work id -> set of book codes it covers, from every .tess file
    under texts/<lang>/ whose name starts with `prefix`."""
    out = {}
    lang_dir = os.path.join(TEXTS_DIR, lang)
    if not os.path.isdir(lang_dir):
        return out
    for filename in sorted(os.listdir(lang_dir)):
        if not filename.endswith('.tess') or not filename.startswith(prefix):
            continue
        stem = filename[:-5]
        coarse = norm_work(stem)
        book = book_of_filename(stem)
        if not book:
            continue
        out.setdefault(coarse, set()).add(book)
    return out


def main():
    write = '--write' in sys.argv

    by_version = {}
    for version, (lang, prefix) in VERSIONS.items():
        by_version[version] = {
            'lang': lang,
            'books': collection_books(lang, prefix),
        }
        n_works = len(by_version[version]['books'])
        n_books = len({b for books in by_version[version]['books'].values() for b in books})
        print(f'{version}: {n_works} work(s), {n_books} distinct book(s)')

    pair_reasons = {}   # (work_a, work_b) sorted -> set of book codes
    pair_langs = {}
    for va, vb in itertools.combinations(VERSIONS, 2):
        books_a = by_version[va]['books']
        books_b = by_version[vb]['books']
        lang_a, lang_b = by_version[va]['lang'], by_version[vb]['lang']
        for work_a, codes_a in books_a.items():
            for work_b, codes_b in books_b.items():
                shared = codes_a & codes_b
                if not shared:
                    continue
                key = tuple(sorted((work_a, work_b)))
                # work_a/work_b sides must track which language goes where.
                if key[0] == work_a:
                    pair_langs[key] = (lang_a, lang_b)
                else:
                    pair_langs[key] = (lang_b, lang_a)
                pair_reasons.setdefault(key, set()).update(shared)

    pairs = list(HAND_ADDED)
    for (work_a, work_b), books in sorted(pair_reasons.items()):
        lang_a, lang_b = pair_langs[(work_a, work_b)]
        codes = ', '.join(sorted(books))
        pairs.append({
            'work_a': work_a, 'work_b': work_b,
            'language_a': lang_a, 'language_b': lang_b,
            'reason': f'scripture translation ({codes})',
        })

    print(f'\n{len(pairs) - len(HAND_ADDED)} scripture pairs generated '
         f'({len(HAND_ADDED)} hand-added literary pair kept), {len(pairs)} total.')

    # The three cells NC named, checked directly.
    checks = [
        ('world_english_bible.pentateuch', 'hebrew_bible.genesis'),
        ('world_english_bible.pentateuch', 'hebrew_bible.leviticus'),
        ('world_english_bible.pentateuch', 'hebrew_bible.numbers'),
        ('world_english_bible.pentateuch', 'hebrew_bible.deuteronomy'),
        ('world_english_bible.writings', 'hebrew_bible.psalms'),
    ]
    present = {tuple(sorted((p['work_a'], p['work_b']))) for p in pairs}
    for a, b in checks:
        key = tuple(sorted((a, b)))
        print(f'  {"OK " if key in present else "MISSING"} {a} <-> {b}')

    out = {
        'generated_from': ('scripts/generate_scripture_translation_pairs.py, from '
                          'backend/scripture_id.py\'s book-name table and the actual '
                          '.tess files under texts/, for every pair of the seven scripture '
                          'versions (Hebrew, Septuagint, Greek NT, Vulgate, Bohairic, '
                          'Sahidic, World English Bible) -- not sampled, exhaustive. Plus '
                          'one hand-added literary pair (Eobanus/Homer).'),
        'note': ('Curated translation/paraphrase pairs. A pair here or matching the '
                'heuristic in aligned_candidates.txt is treated as a translation pair by '
                'the connections map UI (hidden by default).'),
        'count': len(pairs),
        'pairs': pairs,
    }
    if write:
        with open(OUT_PATH, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
            fh.write('\n')
        print(f'\nwrote {OUT_PATH}')
    else:
        print('\n(dry run -- pass --write to save)')


if __name__ == '__main__':
    main()
