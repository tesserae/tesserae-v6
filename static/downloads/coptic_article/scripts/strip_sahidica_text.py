"""Replace Sahidica New Testament line text with verse references.

The Sahidica New Testament ((c) 2000-2006 J. Warren Wells) is licensed for
academic use only, so this release does not redistribute its line text. This
script is what produced the released Shenoute CSV from the raw fusion output:
any text column whose reference belongs to a Sahidica NT book is replaced by
the marker "[Sahidica text omitted per license; see <ref>]". CC-licensed text
(the Sahidic Old Testament, Shenoute) is left in place. The ranked outputs
for Hebrews x Psalms and Romans x Isaiah carry references and scores only,
so nothing needed stripping there.
"""
import csv
import sys

SAHIDICA_PREFIX = 'sahidica.'


def strip_csv(path_in, path_out, ref_col, text_col):
    with open(path_in, newline='') as f:
        rows = list(csv.DictReader(f))
    n = 0
    for row in rows:
        if row.get(ref_col, '').startswith(SAHIDICA_PREFIX) and row.get(text_col):
            row[text_col] = f'[Sahidica text omitted per license; see {row[ref_col]}]'
            n += 1
    with open(path_out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f'{path_out}: {n} of {len(rows)} rows stripped')


if __name__ == '__main__':
    strip_csv(sys.argv[1], sys.argv[2], 'bible_ref', 'bible_text')
