#!/usr/bin/env python3
"""Carry the WEB Greek New Testament alignment onto the SBLGNT texts.

The 27 files grc__new_testament.<book>.json (World English Bible, pipeline 2)
are keyed to the legacy Greek NT corpus files texts/grc/new_testament.*.tess.
The SBL Greek New Testament shipped 2026-08-21 as
texts/grc/novum_testamentum.*.tess with no translations. Both reference schemes
end in chapter.verse, so no alignment search is needed: each SBLGNT ref takes
the English unit the legacy file already holds for the same chapter and verse.

Versification differs in exactly four places, all handled explicitly below and
all checked against the Greek by hand before being written:

- Matt 23:13   SBLGNT numbers the "shut up the Kingdom" woe 23:13; the legacy
               text and the WEB number it 23:14 (and SBLGNT has no 23:14).
- Rev 12:18    "he stood on the sand of the sea": a separate verse in SBLGNT,
               folded into 13:1 by the WEB.
- 3 John 1:15  "Peace be to you...": a separate verse in SBLGNT, folded into
               1:14 by the WEB.
- Rom 16:24    absent from the legacy Greek entirely, so pipeline 2 never
               stored its English; the WEB verse is supplied directly here.

Run from the repo root. Reads and writes data/translations/ (override with
TESSERAE_TRANSLATIONS); reads texts/grc/ (override with TESSERAE_TEXTS, which
names the texts/ directory as in the other aligners).

Coverage after the four fixes is 1.0000 on all 27 books. Any book below 0.95
is a failure to investigate, not to ship (see README: wrong English beside
right Greek is invisible).
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TDIR = os.environ.get('TESSERAE_TRANSLATIONS', os.path.join(ROOT, 'data', 'translations'))
GRC = os.path.join(os.environ.get('TESSERAE_TEXTS', os.path.join(ROOT, 'texts')), 'grc')

MAP = {  # legacy new_testament.<x> -> novum_testamentum.<y>
    'acts': 'actus_apostolorum', 'colossians': 'ad_colossenses',
    'i_corinthinians': 'ad_corinthios_i', 'ii_corinthinians': 'ad_corinthios_ii',
    'ephesians': 'ad_ephesios', 'galatians': 'ad_galatas', 'hebrews': 'ad_hebraeos',
    'philemon': 'ad_philemonem', 'philippians': 'ad_philippenses', 'romans': 'ad_romanos',
    'i_thessalonians': 'ad_thessalonicenses_i', 'ii_thessalonians': 'ad_thessalonicenses_ii',
    'i_timothy': 'ad_timotheum_i', 'ii_timothy': 'ad_timotheum_ii', 'titus': 'ad_titum',
    'revelation': 'apocalypsis', 'james': 'iacobi', 'john': 'ioannes',
    'i_john': 'ioannis_i', 'ii_john': 'ioannis_ii', 'iii_john': 'ioannis_iii',
    'jude': 'iudae', 'luke': 'lucas', 'mark': 'marcus', 'mathew': 'matthaeus',
    'ii_peter': 'petri_ii', 'i_peter': 'petri_i'}

CV = re.compile(r'(\d+)\.(\d+)\s*$')

# SBLGNT chapter.verse -> legacy chapter.verse where the numbering differs but
# the WEB English unit genuinely contains the verse.
REDIRECT = {
    'matthaeus': {(23, 13): (23, 14)},
    'apocalypsis': {(12, 18): (13, 1)},
    'ioannis_iii': {(1, 15): (1, 14)},
}
# Verses in SBLGNT with no legacy Greek line at all, supplied directly from the
# public-domain World English Bible.
EXTRA_UNITS = {
    'ad_romanos': {(16, 24): 'The grace of our Lord Jesus Christ be with you all. Amen.'},
}


def refs_of(tessfile):
    out = []
    with open(tessfile, encoding='utf-8') as fh:
        for line in fh:
            m = re.match(r'<([^>]+)>', line)
            if m:
                out.append(m.group(1))
    return out


def cv(ref):
    m = CV.search(ref)
    return (int(m.group(1)), int(m.group(2))) if m else None


def main():
    sbl_files = {f[:-5].split('novum_testamentum.')[1]: f
                 for f in os.listdir(GRC)
                 if f.startswith('novum_testamentum.') and f.endswith('.tess')}
    missing = set(MAP.values()) ^ set(sbl_files)
    assert not missing, f'book map does not match texts/grc: {missing}'

    failures = []
    for legacy, sbl in sorted(MAP.items()):
        src = json.load(open(os.path.join(TDIR, f'grc__new_testament.{legacy}.json')))
        legacy_cv = {}
        for ref, i in src['ref_to_unit'].items():
            k = cv(ref)
            if k:
                legacy_cv[k] = i
        sbl_refs = refs_of(os.path.join(GRC, sbl_files[sbl]))
        units = list(src['units'])
        redirect = REDIRECT.get(sbl, {})
        extra = EXTRA_UNITS.get(sbl, {})
        ref_to_unit, unmatched = {}, []
        for ref in sbl_refs:
            k = redirect.get(cv(ref), cv(ref))
            i = legacy_cv.get(k)
            if i is None and k in extra:
                units.append(extra[k])
                i = len(units) - 1
            if i is None:
                unmatched.append(ref)
            else:
                ref_to_unit[ref] = i
        n = len(sbl_refs)
        coverage = round(len(ref_to_unit) / n, 4) if n else 0
        out = dict(src)
        out['tess_work'] = f'grc/novum_testamentum.{sbl}'
        out['n_tess_refs'] = n
        out['n_translated'] = len(ref_to_unit)
        out['coverage'] = coverage
        out['note'] = ('Verse-level remap of the legacy WEB alignment '
                       f'(grc/new_testament.{legacy}) onto the SBLGNT text, 2026-08-28. '
                       'Verses absent from the SBLGNT critical text are unmatched.')
        out['units'] = units
        out['n_units_stored'] = len(units)
        out['ref_to_unit'] = ref_to_unit
        flag = ''
        if coverage < 0.95:
            failures.append(sbl)
            flag = '  <-- BELOW 0.95, NOT WRITTEN'
        else:
            fn = f'grc__novum_testamentum.{sbl}.json'
            with open(os.path.join(TDIR, fn), 'w', encoding='utf-8') as fh:
                json.dump(out, fh, ensure_ascii=False)
        print(f'{sbl:28s} refs={n:5d} matched={len(ref_to_unit):5d} '
              f'cov={coverage:.4f} unmatched={len(unmatched)}{flag}')
        for r in unmatched[:10]:
            print(f'    unmatched: {r}')
    if failures:
        raise SystemExit(f'books below 0.95 coverage, investigate: {failures}')


if __name__ == '__main__':
    main()
