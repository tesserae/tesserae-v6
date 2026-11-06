#!/usr/bin/env python3
"""Dio Chrysostom, Orations 1 to 80: the Loeb translation of J. W. Cohoon and
H. Lamar Crosby (1932 to 1951) aligned to texts/grc/dio_chrysostom.orationes.tess.

Source: Bill Thayer's LacusCurtius transcription of the five Loeb volumes
(penelope.uchicago.edu/Thayer/E/Roman/Texts/Dio_Chrysostom/Discourses/<n>*.html,
one page per discourse, 77 and 78 together). The pages mark every section
(`<A CLASS="sec" NAME="2">`); section 1 has no marker and runs from the start
of the body to the marker of section 2. The numbering is von Arnim's, which
the Perseus Greek (tlg0612.tlg001.perseus-grc2) also uses, so the alignment
is by exact citation: Greek `<dio chrys. or. 7.12>` takes the English of
section 12 of discourse 7, and 77_78.N takes section N of the combined page.
Footnotes, page numbers and page furniture are removed.

    align_dio_chrysostom.py HTML_DIR TESS OUT_DIR [--dry]

Rights, recorded 2026-10-24. Cohoon and Crosby's Loeb volumes have no
copyright renewal record (research/translations/2026-10-24_renewal_check/
REPORT.md), and the reading adopted is that a Loeb volume with a US imprint and
no renewal is in the US public domain. Each volume's title page was read on its
archive.org scan (identifiers below): all five show "Cambridge, Massachusetts,
Harvard University Press, London, William Heinemann Ltd", first printed 1932,
1939, 1940, 1946 and 1951 (volume I reprinted 1949, II 1950, III 1961). None is
dated after 1963 and none shows a London-only imprint, so no volume is skipped.
"""
import os
import re
import sys
from collections import OrderedDict

from lxml import html as LH

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V                       # noqa: E402
from align_perseus import length_correlation   # noqa: E402
from write_aligned import tess_refs, write_aligned   # noqa: E402

VOLUMES = [
    # (first speech, last speech, volume, translator, first printed, reprint, scan)
    (1, 11, 'I', 'J. W. Cohoon', 1932, 'reprinted 1949', 'in.ernet.dli.2015.281363'),
    (12, 30, 'II', 'J. W. Cohoon', 1939, 'reprinted 1950', 'in.ernet.dli.2015.281364'),
    (31, 36, 'III', 'J. W. Cohoon and H. Lamar Crosby', 1940, 'reprinted 1961', 'in.ernet.dli.2015.281365'),
    (37, 60, 'IV', 'H. Lamar Crosby', 1946, '', 'in.ernet.dli.2015.281366'),
    (61, 80, 'V', 'H. Lamar Crosby', 1951, '', 'in.ernet.dli.2015.281367'),
]
IMPRINT = 'Cambridge, Massachusetts: Harvard University Press; London: William Heinemann Ltd'


def page_sections(path, key):
    """-> OrderedDict 'key.section' -> English."""
    doc = LH.fromstring(open(path, encoding='utf-8', errors='replace').read())
    starts = [p for p in doc.xpath('//p[contains(concat(" ", normalize-space(@class), " "), " start ")]')
              if not p.xpath('ancestor::table')]
    assert starts, f'{path}: no body start paragraph'
    out = OrderedDict()
    sec = '1'
    buf = []

    def flush():
        t = re.sub(r'\s+', ' ', ''.join(buf).replace('\xad', '').replace('⁠', '')).strip()
        if t:
            k = f'{key}.{sec}'
            out[k] = (out[k] + ' ' + t) if k in out else t
        buf.clear()

    def go(node):
        nonlocal sec
        cls = node.get('class')
        if node.tag == 'a' and cls == 'sec':
            flush()
            sec = node.get('name', '').strip()
            return
        if node.tag == 'a' and cls in ('ref', 'note'):
            return
        if node.tag == 'span' and cls == 'pagenum':
            return
        if node.text:
            buf.append(node.text)
        for c in node:
            go(c)
            if c.tail:
                buf.append(c.tail)

    for el in [starts[0]] + list(starts[0].itersiblings()):
        if el.tag == 'hr':
            break
        if el.tag != 'p' or 'ivy' in (el.get('class') or ''):
            continue
        if el.xpath('./a[@class="note"]'):
            break
        go(el)
    flush()
    return out


def main():
    html_dir, tess_path, out_dir = sys.argv[1:4]
    by_ref = OrderedDict()
    for n in list(range(1, 77)) + ['77_and_78', 79, 80]:
        key = '77_78' if n == '77_and_78' else str(n)
        secs = page_sections(os.path.join(html_dir, f'{n}.html'), key)
        by_ref.update(secs)
    print(f'{len(by_ref)} English sections on {79} pages')

    refs = tess_refs(tess_path)
    src = {}
    for line in open(tess_path, encoding='utf-8'):
        ref, text = line.rstrip('\n').split('\t', 1)
        src[ref[1:-1]] = text
    tails = {r: r.split()[-1] for r in refs}
    units, ref_to_unit, pairs, missing, merged = [], {}, [], [], []
    unit_of = {}
    for r in refs:
        t = tails[r]
        if t in by_ref:
            unit_of[t] = len(units)
            ref_to_unit[r] = len(units)
            units.append(by_ref[t])
            pairs.append((src[r], by_ref[t]))
        else:
            # A Greek section whose number the page does not mark (Cohoon ran
            # two or three of von Arnim's sections together) shares the
            # English of the nearest earlier section of the same discourse.
            sp, sc = t.rsplit('.', 1)
            prev = next((f'{sp}.{k}' for k in range(int(sc) - 1, 0, -1) if f'{sp}.{k}' in unit_of), None) \
                if sc.isdigit() else None
            if prev:
                ref_to_unit[r] = unit_of[prev]
                merged.append(r)
            else:
                missing.append(r)
    print(f'{len(merged)} sections share the English of the preceding section')
    extra = [k for k in by_ref if k not in set(tails.values())]
    hit, n = V.score(pairs, 'grc')
    corr = length_correlation(pairs)
    print(f'refs {len(refs)} translated {len(ref_to_unit)} coverage {len(ref_to_unit) / len(refs):.4f}')
    print(f'Greek refs with no English: {len(missing)} e.g. {[m.split()[-1] for m in missing[:12]]}')
    print(f'English sections with no Greek: {len(extra)} e.g. {extra[:12]}')
    print(f'name check {hit} on {n}; length correlation {corr}')
    if len(sys.argv) > 4 and sys.argv[4] == '--dry':
        return
    sources = [{
        'translator': tr, 'year': yr, 'publisher': 'Harvard University Press / William Heinemann',
        'title': f'Dio Chrysostom (Loeb Classical Library), volume {vol}, discourses {a} to {b}',
        'mode': 'exact', 'ref_composition': ['discourse', 'section'],
        'imprint': IMPRINT, 'edition_note': f'first printed {yr}' + (f', {rp}' if rp else ''),
        'archive_org_scan_read': scan,
        'source_url': 'https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Dio_Chrysostom/home.html',
        'pd_reason': 'public domain, US, copyright not renewed (renewal check 2026-10-24)',
        'short_attribution': f'{tr} (Loeb, {yr})'}
        for a, b, vol, tr, yr, rp, scan in VOLUMES]
    path = write_aligned(
        out_dir, 'grc', 'dio_chrysostom.orationes', units, ref_to_unit,
        attribution='J. W. Cohoon and H. Lamar Crosby (Loeb Classical Library, 1932 to 1951); '
                    'transcription by Bill Thayer, LacusCurtius',
        license='public domain, US, copyright not renewed (renewal check 2026-10-24)',
        sources=sources, confidence='high' if (hit or 0) >= 0.70 else 'medium',
        approximate=False, tess_refs=refs,
        notes=f'{len(merged)} sections whose number the transcription does not mark share the English of the preceding section of the same discourse; {len(missing)} Greek references have no English.',
        name_check={'name_check_hit_rate': hit, 'name_check_n': n},
        verified_by=('exact citation match; proper names; length correlation '
                     f'{corr:.3f}') if corr is not None else 'exact citation match')
    print('wrote', path)


if __name__ == '__main__':
    main()
