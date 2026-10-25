#!/usr/bin/env python3
"""Fathers of the Greek tranche of 2026-10-24: Ante-Nicene and Nicene and
Post-Nicene Fathers translations aligned by the chapter or section number the
translation prints.

    Justin Martyr, First and Second Apology, Dialogue with Trypho   ANF 1 (Dods and Reith, 1885)
    Tatian, Address to the Greeks                                   ANF 2 (J. E. Ryland, 1885)
    Theophilus, To Autolycus                                        ANF 2 (Marcus Dods, 1885)
    Athenagoras, Plea for the Christians, Resurrection of the Dead  ANF 2 (B. P. Pratten, 1885)
    Origen, Against Celsus                                          ANF 4 (Frederick Crombie, 1885)
    Athanasius, On the Incarnation                                  NPNF 2.4 (Archibald Robertson, 1892)
    Athanasius, Discourses against the Arians I to IV               NPNF 2.4 (J. H. Newman, revised by A. Robertson, 1892)

Source: the Christian Classics Ethereal Library's ThML files
(ccel.org/ccel/schaff/anf01.xml, anf02.xml, anf04.xml, npnf204.xml). A chapter
is a div whose first words read "Chapter N" (an unnumbered chapter takes its
order in its book). The Discourses print Newman's paragraph numbers inside the
text ("22. The ..."), which are found in order, so a Greek line cited by
paragraph takes the English of that paragraph. A Greek line cited deeper than
the English (Justin's Dialogue has 752 sections, the English 142 chapters)
shares the English of its chapter. Footnotes are dropped.

    align_ccel_fathers.py WORK_STEM THML TESS OUT_DIR [--dry]
"""
import os
import re
import sys

from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V                       # noqa: E402
from align_perseus import length_correlation   # noqa: E402
from write_aligned import tess_refs, write_aligned   # noqa: E402
from align_ccel_histories import roman, text_of   # noqa: E402

ANF = 'Ante-Nicene Fathers'
CFG = {
    'justin_martyr.apologia_i': dict(kind='chapters', d1='JUSTIN MARTYR', d2='The First Apology', depth=1, translator='M. Dods and G. Reith', year=1885,
                                     title='The First Apology (Ante-Nicene Fathers, vol. 1)', url='https://ccel.org/ccel/schaff/anf01.html'),
    'justin_martyr.apologia_ii': dict(kind='chapters', d1='JUSTIN MARTYR', d2='The Second Apology', depth=1, translator='M. Dods and G. Reith', year=1885,
                                      title='The Second Apology (Ante-Nicene Fathers, vol. 1)', url='https://ccel.org/ccel/schaff/anf01.html'),
    'justin_martyr.dialogus_cum_tryphone': dict(kind='chapters', d1='JUSTIN MARTYR', d2='Dialogue with Trypho', depth=1, translator='M. Dods and G. Reith', year=1885,
                                                title='Dialogue with Trypho (Ante-Nicene Fathers, vol. 1)', url='https://ccel.org/ccel/schaff/anf01.html'),
    'tatian.oratio_ad_graecos': dict(kind='chapters', d1='TATIAN', d2='Address to the Greeks', depth=1, translator='J. E. Ryland', year=1885,
                                     title='Address to the Greeks (Ante-Nicene Fathers, vol. 2)', url='https://ccel.org/ccel/schaff/anf02.html'),
    'athenagoras.legatio': dict(kind='chapters', d1='ATHENAGORAS', d2='A Plea for the Christians', depth=1, translator='B. P. Pratten', year=1885,
                                title='A Plea for the Christians (Ante-Nicene Fathers, vol. 2)', url='https://ccel.org/ccel/schaff/anf02.html'),
    'athenagoras.de_resurrectione': dict(kind='chapters', d1='ATHENAGORAS', d2='The Resurrection of the Dead', depth=1, translator='B. P. Pratten', year=1885,
                                         title='The Resurrection of the Dead (Ante-Nicene Fathers, vol. 2)', url='https://ccel.org/ccel/schaff/anf02.html'),
    'theophilus_of_antioch.ad_autolycum': dict(kind='books', d1='THEOPHILUS', d2='Theophilus to Autolycus', translator='Marcus Dods', year=1885,
                                               title='Theophilus to Autolycus (Ante-Nicene Fathers, vol. 2)', url='https://ccel.org/ccel/schaff/anf02.html'),
    'origen.contra_celsum': dict(kind='books', d1='Origen', d2='Origen Against Celsus', translator='Frederick Crombie', year=1885,
                                 title='Origen against Celsus (Ante-Nicene Fathers, vol. 4)', url='https://ccel.org/ccel/schaff/anf04.html'),
    'athanasius.de_incarnatione': dict(kind='chapters', d1='The Incarnation of the Word', d2='On the Incarnation of the Word', depth=1, translator='Archibald Robertson', year=1892,
                                       title='On the Incarnation of the Word (Nicene and Post-Nicene Fathers, series 2, vol. 4)', url='https://ccel.org/ccel/schaff/npnf204.html'),
}
for n, rom in (('i', 'xxi.ii.i'), ('ii', 'xxi.ii.iii'), ('iii', 'xxi.ii.iv'), ('iv', 'xxi.ii.vi')):
    CFG[f'athanasius.contra_arianos_{n}'] = dict(
        kind='paragraphs', div3=rom, translator='J. H. Newman, revised by A. Robertson', year=1892,
        title=f'Discourse {n.upper()} against the Arians (Nicene and Post-Nicene Fathers, series 2, vol. 4)',
        url='https://ccel.org/ccel/schaff/npnf204.html')


def load(path):
    return etree.parse(path, etree.XMLParser(recover=True, huge_tree=True, load_dtd=False, resolve_entities=False)).getroot()


def chapter_number(text, order):
    m = re.match(r'(?:Chapter|CHAPTER)\s+([IVXLC]+|\d+)\b', text)
    if m:
        g = m.group(1)
        return (int(g) if g.isdigit() else roman(g)), text[m.end():].lstrip(' .—-')
    return order, text


def strip_heading(text):
    # the chapter's argument runs up to the first numbered paragraph or sentence; keep it, it is English of the chapter
    return text


def extract_chapters(root, cfg):
    d1 = next(d for d in root.iter('div1') if cfg['d1'] in (d.get('title') or ''))
    d2 = next(d for d in d1.findall('div2') if (d.get('title') or '').strip().startswith(cfg['d2']))
    out, order = {}, 0
    for d3 in d2.findall('div3'):
        order += 1
        t = text_of(d3)
        n, body = chapter_number(t, order)
        out[str(n)] = (out.get(str(n), '') + ' ' + body).strip()
    return out


def extract_books(root, cfg):
    d1 = next(d for d in root.iter('div1') if cfg['d1'] in (d.get('title') or ''))
    d2 = next(d for d in d1.findall('div2') if (d.get('title') or '').strip().startswith(cfg['d2']))
    out = {}
    for d3 in d2.findall('div3'):
        m = re.match(r'(?:Book )?([IVX]+)\.?$', (d3.get('title') or '').strip())
        if not m:
            continue
        book = roman(m.group(1))
        order = 0
        for d4 in d3.findall('div4'):
            t4 = text_of(d4)
            if (d4.get('title') or '').strip().lower().startswith('preface'):
                # the Prologue: Greek <orig. cels. 0.N> takes the Preface of book 1
                body = re.sub(r'^.*?Preface\.\s*', '', t4, count=1)
                out['0'] = (out.get('0', '') + ' ' + body).strip()
                continue
            order += 1
            n, body = chapter_number(t4, order)
            k = f'{book}.{n}'
            out[k] = (out.get(k, '') + ' ' + body).strip()
    return out


def extract_paragraphs(root, cfg):
    d3 = next(d for d in root.iter('div3') if d.get('id') == cfg['div3'])
    t = text_of(d3)
    out, pos, k = {}, 0, 1
    marks = []
    while k < 400:
        found = None
        for cand in (k, k + 1, k + 2):
            m = re.compile(r'(?:(?<=\s)|^)%d\.\s+(?=[A-Z‘“"(\[])' % cand).search(t, pos)
            if m and (found is None or m.start() < found[1].start()):
                found = (cand, m)
        if not found:
            break
        marks.append((found[0], found[1].start(), found[1].end()))
        pos, k = found[1].end(), found[0] + 1
    for i, (n, a, b) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(t)
        out[str(n)] = t[b:end].strip()
    return out


def main():
    stem, thml, tess_path, out_dir = sys.argv[1:5]
    cfg = CFG[stem]
    root = load(thml)
    by = {'chapters': extract_chapters, 'books': extract_books, 'paragraphs': extract_paragraphs}[cfg['kind']](root, cfg)
    src = {}
    for line in open(tess_path, encoding='utf-8'):
        ref, text = line.rstrip('\n').split('\t', 1)
        src[ref[1:-1]] = text
    refs = tess_refs(tess_path)
    units, ref_to_unit, unit_of, missing, groups = [], {}, {}, [], {}
    for r in refs:
        tail = r.split()[-1]
        cand = tail
        while cand not in by and '.' in cand:
            cand = cand.rsplit('.', 1)[0]
        if cand not in by:
            missing.append(r)
            continue
        if cand not in unit_of:
            unit_of[cand] = len(units)
            units.append(by[cand])
        ref_to_unit[r] = unit_of[cand]
        groups.setdefault(cand, []).append(src[r])
    pairs = [(' '.join(g), by[k]) for k, g in groups.items()]
    hit, n = V.score(pairs, 'grc')
    corr = length_correlation(pairs)
    cov = len(ref_to_unit) / len(refs)
    extra = [k for k in by if k not in groups]
    print(f'{stem}: refs {len(refs)} translated {len(ref_to_unit)} ({cov:.4f}); English units {len(by)}, with Greek {len(groups)}')
    print(f'  Greek refs with no English {len(missing)} e.g. {[m.split()[-1] for m in missing[:8]]}')
    print(f'  English units with no Greek {len(extra)} e.g. {extra[:8]}')
    print(f'  name check {hit} on {n}; length correlation {corr}')
    if '--dry' in sys.argv:
        return
    if cov < 0.85 or (corr is not None and corr < 0.5):
        print('  REFUSE: coverage under 85 percent or length correlation under 0.5')
        return
    path = write_aligned(
        out_dir, 'grc', stem, units, ref_to_unit,
        attribution=f"{cfg['translator']} ({'Ante-Nicene' if 'Ante' in cfg['title'] else 'Nicene and Post-Nicene'} Fathers); Christian Classics Ethereal Library",
        license=f"Public domain (published {cfg['year']}).",
        sources=[{'translator': cfg['translator'], 'year': cfg['year'], 'publisher': 'Christian Literature Publishing Co.',
                  'title': cfg['title'], 'mode': 'chapter', 'source_url': cfg['url'],
                  'pd_reason': f"published {cfg['year']}, public domain", 'short_attribution': f"{cfg['translator']} ({cfg['year']})"}],
        confidence='high' if (corr or 0) >= 0.8 else 'medium', approximate=False, tess_refs=refs,
        notes=f'Aligned by the chapter or paragraph number the translation prints; Greek lines cited deeper than the English share its unit. {len(missing)} Greek lines have no English.',
        name_check={'name_check_hit_rate': hit, 'name_check_n': n},
        verified_by='chapter or paragraph number; proper names; length correlation '
                    f'{corr:.3f}' if corr is not None else 'chapter or paragraph number')
    print('  wrote', path)


if __name__ == '__main__':
    main()
