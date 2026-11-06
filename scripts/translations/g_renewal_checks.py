#!/usr/bin/env python3
"""Renewal searches for the volumes of Part G (2026-10-25), one row per volume.

Uses renewal_search.batch (the NYPL cce-renewals data, 1954 to 1991, which holds the printed
Catalog of Copyright Entries renewal volumes and the Copyright Office database). A Loeb volume
first published 1931 to 1963 with a United States imprint and no renewal found is treated as
United States public domain; a volume of 1930 or earlier is public domain by date in 2026.

    g_renewal_checks.py OUT.tsv

Prints every hit (first 12 per query) and writes one TSV row per query with the count. Nothing
found means no renewal in this dataset, which is the evidence, not a proof.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renewal_search as R   # noqa: E402

QUERIES = [
    # label, title regex, translator regex
    ('Demosthenes vol. III (Vince 1935): Meidias, Androtion, Aristocrates, Timocrates, Aristogeiton', 'demosthenes', 'vince'),
    ('Demosthenes vols. IV to VI (Murray 1936, 1939): private orations', 'demosthenes', 'murray'),
    ('Demosthenes vol. VII (DeWitt and DeWitt 1949): Funeral Speech, Erotic Essay, Exordia, Letters', 'demosthenes', 'dewitt'),
    ('Demosthenes, any translator, title words of the Loeb series', 'demosthenes.{0,60}(loeb|heinemann|harvard)', None),
    ('Demosthenes, author only', 'demosthenes', None),
    ('Isocrates vol. III (Van Hook 1945)', 'isocrates', 'van hook|vanhook'),
    ('Isocrates, author only', 'isocrates', None),
    ('Plato, Republic (Shorey 1930, 1935)', 'republic', 'shorey'),
    ('Plato, Shorey, any title', 'plato', 'shorey'),
    ('Plato, Loeb volumes (Lamb, Bury, Fowler)', 'plato', 'lamb|bury|fowler'),
    ('Plato Alcibiades, Lovers (Lamb 1927)', 'alcibiades|lovers|plato', 'lamb'),
    ('Plato Epistles (Bury 1929)', 'plato|epistles|letters', 'bury'),
    ('Loeb Classical Library, any entry', 'loeb classical', None),
    ('Heinemann, any entry naming Demosthenes, Isocrates or Plato', 'heinemann', 'demosthenes|isocrates|plato'),
]
if __name__ == '__main__':
    out = sys.argv[1]
    res = R.batch(QUERIES)
    with open(out, 'w') as f:
        f.write('label\ttitle_regex\ttranslator_regex\thits\tfirst_hits\n')
        for label, t, s, hits in res:
            print(f'== {label}: {len(hits)} hits (title={t!r} translator={s!r})')
            for fn, b in hits[:12]:
                print('   ', fn, '|', b[:170].replace('\n', ' '))
            f.write(f'{label}\t{t}\t{s}\t{len(hits)}\t' + ' || '.join(b[:120].replace('\t', ' ') for fn, b in hits[:5]) + '\n')
