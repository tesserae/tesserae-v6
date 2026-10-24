#!/usr/bin/env python3
"""Exact-citation alignment of Perseus English TEI to the Greek tranche files
of 2026-10-24: Diogenes Laertius (Hicks, Loeb 1925) and the four Apostolic
Fathers texts that Perseus holds in English only (Clement of Rome 1 and 2, the
Didache, Hermas and Ignatius, in Kirsopp Lake's Loeb translation, 1912 to
1917). The Perseus English cites by the same book, chapter and section as the
First1KGreek and Perseus Greek, so Greek `<ign. 3.2.1>` takes the English of
epistle 3, chapter 2, section 1. A division labelled prol, pref or sal in the
English is chapter 0 in the Greek file. A Greek line cited deeper than the
English (Diogenes 5.5.81.3, an item of a list of works) shares the English of
its parent section.

    align_perseus_exact_grc_tranche.py WORK_STEM ENG.xml TESS OUT_DIR [--dry]

Refuses to write unless at least 95 percent of the Greek lines have English.
Reports the proper-name and length-correlation checks of the other aligners.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V                       # noqa: E402
import tei_extract_base as E                   # noqa: E402
from align_perseus import length_correlation   # noqa: E402
from write_aligned import tess_refs, write_aligned   # noqa: E402

PREF = {'prol': '0', 'pref': '0', 'sal': '0', 'pr': '0', 'praef': '0'}
INFO = {
    'diogenes_laertius.vitae_philosophorum': dict(
        urn='urn:cts:greekLit:tlg0004.tlg001.perseus-eng2', translator='R. D. Hicks', year=1925,
        title='Diogenes Laertius, Lives of Eminent Philosophers (Loeb Classical Library)',
        file='canonical-greekLit/data/tlg0004/tlg001/tlg0004.tlg001.perseus-eng2.xml', short='R. D. Hicks (Loeb, 1925)',
        pd='Loeb volumes of 1925, US public domain'),
}
for stem, tl, tag in [('ignatius.epistulae', 'tlg1443.tlg001', 'Lake'), ('clement_of_rome.epistula_i_ad_corinthios', 'tlg1271.tlg001', 'Lake'),
                      ('clement_of_rome.epistula_ii_ad_corinthios', 'tlg1271.tlg002', 'Lake'),
                      ('didache.didache', 'tlg1311.tlg001', 'Lake'), ('hermas.pastor', 'tlg1419.tlg001', 'Lake')]:
    t = tl.split('.')
    INFO[stem] = dict(urn=f'urn:cts:greekLit:{tl}.perseus-eng1', translator='Kirsopp Lake', year=(1913 if stem == 'hermas.pastor' else 1912),
                      title='The Apostolic Fathers (Loeb Classical Library)',
                      file=f'canonical-greekLit/data/{t[0]}/{t[1]}/{tl}.perseus-eng1.xml', short='K. Lake (Loeb, 1912-1913)',
                      pd='Loeb volumes of 1912 to 1913, US public domain')


def main():
    stem, eng_path, tess_path, out_dir = sys.argv[1:5]
    meta, chunks = E.extract(eng_path)
    labels = meta['ref_labels']
    by_ref = {}
    for c in chunks:
        a = c['anchors']
        key = '.'.join(PREF.get(a.get(l, ''), a.get(l, '')) for l in ('book', 'epistle', 'chapter', 'section') if l in a)
        by_ref[key] = by_ref.get(key, '') + (' ' if key in by_ref else '') + c['text']
    src = {}
    for line in open(tess_path, encoding='utf-8'):
        ref, text = line.rstrip('\n').split('\t', 1)
        src[ref[1:-1]] = text
    refs = tess_refs(tess_path)
    units, ref_to_unit, pairs, missing, unit_of = [], {}, [], [], {}
    for r in refs:
        tail = r.split()[-1]
        cand = tail
        # a preface or salutation: Greek 3.0.1 or preface.1, English 3.0.0 or 0.0
        for a, b in (('.0.1', '.0.0'), ('preface.1', '0.0')):
            if cand.endswith(a) and cand[:-len(a)] + b in by_ref and cand not in by_ref:
                cand = cand[:-len(a)] + b
        while cand not in by_ref and '.' in cand:
            cand = cand.rsplit('.', 1)[0]            # deeper than the English: share the parent's
        if cand not in by_ref:
            # Greek has no number the English marks: leave uncovered
            missing.append(r)
            continue
        if cand not in unit_of:
            unit_of[cand] = len(units)
            units.append(by_ref[cand])
        ref_to_unit[r] = unit_of[cand]
        if cand == tail or cand.endswith('.0.0') or cand == '0.0':   # a shared parent would skew the length check
            pairs.append((src[r], by_ref[cand]))
    tails = {r.split()[-1] for r in refs}
    extra = [k for k in by_ref if not any(t == k or t.startswith(k + '.') for t in tails)]
    hit, n = V.score(pairs, 'grc')
    corr = length_correlation(pairs)
    cov = len(ref_to_unit) / len(refs)
    print(f'{stem}: refs {len(refs)} translated {len(ref_to_unit)} ({cov:.4f}) English labels {labels}')
    print(f'  Greek refs with no English {len(missing)} e.g. {[m.split()[-1] for m in missing[:8]]}')
    print(f'  English sections with no Greek {len(extra)} e.g. {extra[:8]}')
    print(f'  name check {hit} on {n}; length correlation {corr}')
    if '--dry' in sys.argv or cov < 0.95:
        if cov < 0.95:
            print('  REFUSE: coverage under 95 percent')
        return
    i = INFO[stem]
    path = write_aligned(
        out_dir, 'grc', stem, units, ref_to_unit,
        attribution='Perseus Digital Library, Tufts University',
        license=f'CC BY-SA 4.0 (Perseus Digital Library TEI); underlying translation is US public domain ({i["pd"]})',
        sources=[{'cts_urn': i['urn'], 'translator': i['translator'], 'year': i['year'],
                  'publisher': 'Harvard University Press / William Heinemann', 'title': i['title'],
                  'mode': 'exact', 'pd_reason': i['pd'], 'source_file': i['file'], 'short_attribution': i['short']}],
        confidence='high' if (hit or 0) >= 0.5 or (corr or 0) >= 0.8 else 'medium', approximate=False, tess_refs=refs,
        notes=f'{len(missing)} Greek lines have no English of their own.',
        name_check={'name_check_hit_rate': hit, 'name_check_n': n},
        verified_by='exact citation match; proper names; length correlation '
                    f'{corr:.3f}' if corr is not None else 'exact citation match')
    print('  wrote', path)


if __name__ == '__main__':
    main()
