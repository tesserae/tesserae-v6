#!/usr/bin/env python3
"""Share of the documents collection that carries each family of published
edition reference, as read by backend.document_citations from the
principal_edition column of metadata.db (read-only). A recognised citation of
a family can be linked to a held document only for documents counted here.

    python scripts/documents/measure_edition_coverage.py [metadata.db]
"""
import collections
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.document_citations import find_document_citations, DocumentEditionIndex  # noqa: E402

DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       'data', 'documents', 'metadata.db')


def main(path):
    conn = sqlite3.connect('file:%s?mode=ro&immutable=1' % path, uri=True)
    rows = conn.execute('SELECT id, source, principal_edition FROM documents').fetchall()
    total = collections.Counter(r[1] for r in rows)
    fam = collections.defaultdict(collections.Counter)
    anyc = collections.Counter()
    has_ed = collections.Counter()
    unmatched = collections.Counter()
    for _id, src, pe in rows:
        if not pe:
            continue
        has_ed[src] += 1
        cs = find_document_citations(pe)
        if cs:
            anyc[src] += 1
        else:
            m = re.match(r'[^\s,.;(]+', pe)
            unmatched[m.group(0) if m else pe[:10]] += 1
        for f in {c['family'] for c in cs}:
            fam[f][src] += 1
    N = len(rows)
    print('documents: %d' % N)
    print('sources: ' + ', '.join('%s %d' % kv for kv in sorted(total.items())))
    print('with principal_edition: %d (%.1f%%)' % (sum(has_ed.values()), 100.0 * sum(has_ed.values()) / N))
    print('with a recognised edition reference: %d (%.1f%%)' % (sum(anyc.values()), 100.0 * sum(anyc.values()) / N))
    print('\nfamily  docs  %%all   by source (docs, %% of source)')
    for f, c in sorted(fam.items(), key=lambda kv: -sum(kv[1].values())):
        n = sum(c.values())
        print('%-7s %6d %5.1f%%  ' % (f, n, 100.0 * n / N) + ', '.join(
            '%s %d (%.1f%%)' % (s, v, 100.0 * v / total[s]) for s, v in c.most_common()))
    print('\nunrecognised first tokens of principal_edition (top 25):')
    print(unmatched.most_common(25))
    idx = DocumentEditionIndex.from_rows(rows)
    print('\nlookup keys: %d' % len(idx.by_num))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
