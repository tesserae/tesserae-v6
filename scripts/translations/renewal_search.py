#!/usr/bin/env python3
"""Search the NYPL cce-renewals data for one volume's own title and translator.

Part F of the 2026-10-24 translation batch. The data (1954 to 1991 renewal
entries, tab-separated) is a local download in ~/tesserae-backups/
renewal_check_2026-10-24/nypl/. A renewal of a 1931 to 1963 book fell due in the
28th year after publication, so a book published in 1963 was renewable in 1991.

    renewal_search.py TITLE_REGEX [TRANSLATOR_REGEX]

Prints every entry whose row (author, title, claimants, notes, full text) matches
TITLE_REGEX and, when given, TRANSLATOR_REGEX, then the count. Entries are
matched case-insensitively. Nothing found means no renewal in this dataset, which
is the evidence the alignment rests on, not a proof (the Stanford database could
not be queried, README of the renewal check).
"""
import csv
import glob
import os
import re
import sys

DIR = os.environ.get('RENEWALS', os.path.expanduser('~/tesserae-backups/renewal_check_2026-10-24/nypl'))


def rows():
    csv.field_size_limit(10**7)
    for p in sorted(glob.glob(f'{DIR}/*.tsv')):
        with open(p, encoding='utf-8', errors='replace', newline='') as fh:
            for r in csv.DictReader(fh, delimiter='\t'):
                yield os.path.basename(p), r


def search(title_re, tr_re=None):
    t = re.compile(title_re, re.I)
    s = re.compile(tr_re, re.I) if tr_re else None
    hits = []
    for fn, r in rows():
        # The 1954 to 1977 files and the 1978 to 1991 database files name their
        # columns differently (author/title/notes and auth/titl/note), so the
        # whole row is searched.
        blob = ' '.join(v for v in r.values() if isinstance(v, str))
        if t.search(blob) and (s is None or s.search(blob)):
            hits.append((fn, r))
    return hits


if __name__ == '__main__':
    title_re = sys.argv[1]
    tr_re = sys.argv[2] if len(sys.argv) > 2 else None
    hits = search(title_re, tr_re)
    for fn, r in hits[:25]:
        print(fn, '|', (r.get('full_text') or r.get('title') or r.get('titl') or '')[:230])
    print(f'{len(hits)} entries for title={title_re!r} translator={tr_re!r}')


def batch(queries):
    """[(label, title_re, translator_re_or_None)] with one load of the data.

    Returns [(label, title_re, tr_re, hits)] where hits is a list of entry texts.
    """
    data = [(fn, ' '.join(v for v in r.values() if isinstance(v, str))) for fn, r in rows()]
    out = []
    for label, t, s in queries:
        tr, sr = re.compile(t, re.I), (re.compile(s, re.I) if s else None)
        hits = [(fn, b[:200]) for fn, b in data if tr.search(b) and (sr is None or sr.search(b))]
        out.append((label, t, s, hits))
    return out
