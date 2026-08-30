#!/usr/bin/env python3
"""PD English translations for the 2026-08-30 Latin batches (batch 1 backfill
+ batch 2), structure-keyed against clean transcriptions:

  justin      Watson 1853 (Bohn) via attalus.org: [book.chapter] markers,
              chapter-keyed EXACT (corpus refs are book.chapter).
  velleius    Shipley 1924 (Loeb) via LacusCurtius: <A CLASS="sec"> anchors,
              section-keyed EXACT (refs book.chapter.section).
  strat       Frontinus Strategemata, Bennett 1925 via LacusCurtius:
              chapter + exemplum anchors, keyed EXACT.
  aquis       Frontinus De Aquis, Bennett 1925 via LacusCurtius: section
              anchors (continuous numbering), keyed EXACT.
  sidonius    Dalton 1915 letters via tertullian.org: per-book pages,
              Roman-numeral letter headings, letter-keyed (all sections of
              a letter serve its English).
  varro_rr    Storr-Best 1912 (archive.org OCR): BOOK/chapter structure,
              chapter-keyed with OCR cleanup.
  abelard_hist   Bellows 1922 (PG 14268): chapter headings, chapter-keyed
                 proportional by sentence length.
  abelard_epist  Moncrieff 1925/26 (archive.org OCR): letter headings,
                 letter-keyed proportional.
  gregory_regula NPNF s2 v12 Barmby via CCEL plain text: part/chapter
                 headings, chapter-keyed EXACT.

Each work emits the standard la__<work>.json served by /api/translation.
The name check (proper_names.score) guards every alignment; a work under
0.25 is refused rather than shipped wrong.

Usage: align_batch2.py --work justin --src <dir> --tess <file> --out <json>
"""
import argparse
import html as htmllib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V


def strip_tags(s):
    s = re.sub(r'<script.*?</script>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = htmllib.unescape(s)
    s = s.replace('\xa0', ' ')
    s = re.sub(r'[⁠​‎­]', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def tess_refs(path, prefix):
    refs, lat = [], {}
    pat = re.compile(r'^<(' + re.escape(prefix) + r'\s+([^>]+))>\s*(.*)')
    for line in open(path, encoding='utf-8', errors='replace'):
        m = pat.match(line)
        if m:
            refs.append((m.group(1), m.group(2)))
            lat[m.group(1)] = m.group(3)
    return refs, lat


def emit(out, tess_work, refs, lat, mapping, meta):
    pairs = [(lat[r], t) for r, t in mapping.items()]
    cov = len(mapping) / len(refs)
    hit, n = V.score(pairs, 'la', sample=500)
    ulist, idx, ref2u = [], {}, {}
    for ref, txt in mapping.items():
        if txt not in idx:
            idx[txt] = len(ulist)
            ulist.append(txt)
        ref2u[ref] = idx[txt]
    print(f'{tess_work}: cov {cov:.4f} ({len(mapping)}/{len(refs)}) '
          f'units {len(ulist)} names {hit}/{n}')
    if hit is None or (n >= 20 and hit < 0.25):
        print('REFUSED: name check failed')
        return False
    doc = {'tess_work': tess_work, 'language': 'la',
           'n_tess_refs': len(refs), 'n_translated': len(mapping),
           'coverage': round(cov, 4),
           'mean_source_lines_per_translation_unit':
               round(len(mapping) / max(1, len(ulist)), 1),
           'alignment_confidence': 'high' if (hit or 0) >= 0.5 else 'medium',
           'name_check_hit_rate': hit, 'name_check_n': n,
           'verified_by': 'names',
           'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u}
    doc.update(meta)
    json.dump(doc, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    return True

# ----------------------------------------------------------------- justin

JUSTIN_PAGES = ['attalus_justin8.html', 'attalus_justin9.html',
                'attalus_justin10.html', 'attalus_justin11.html',
                'attalus_justin1.html', 'attalus_justin2.html',
                'attalus_justin3.html', 'attalus_justin4.html',
                'attalus_justin5.html', 'attalus_justin6.html',
                'attalus_justin7.html']


def justin(src, tess, out):
    english = {}
    for pi, page in enumerate(JUSTIN_PAGES):
        t = open(os.path.join(src, 'justin', page), encoding='utf-8',
                 errors='replace').read()
        # cut navigation/footer
        t = re.sub(r'(?s)^.*?<h1', '<h1', t, flags=re.I)
        marks = list(re.finditer(
            r'<(?:FONT|A)[^>]*CLASS="ref"[^>]*>\[(\d+)\.(\d+)\]</(?:FONT|A)>',
            t, flags=re.I))
        if pi == 0 and marks:
            # Watson's translation of Justin's preface precedes [1.1]
            pre = strip_tags(t[:marks[0].start()])
            m = re.search(r'PREFACE\s*\[Preface\]\s*L?\s*', pre)
            if m:
                english[('pref', 1)] = re.sub(
                    r'\s*(\d+)\s*(?=[A-Z"])', ' ',
                    re.sub(r'BOOK 1\s*$', '', pre[m.end():])).strip()
        for k, m in enumerate(marks):
            end = marks[k + 1].start() if k + 1 < len(marks) else len(t)
            chunk = t[m.end():end]
            chunk = re.split(r'<H2', chunk, flags=re.I)[0]
            txt = strip_tags(chunk)
            txt = re.sub(r'\bL\b\s*', '', txt, count=1)  # the Latin-link glyph
            txt = re.sub(r'\s*(\d+)\s*(?=[A-Z"])', ' ', txt)  # verse numbers
            txt = re.sub(r'\s+', ' ', txt).strip()
            if len(txt.split()) >= 3:
                english[(m.group(1), int(m.group(2)))] = txt
    refs, lat = tess_refs(tess, 'iust. epit.')
    mapping = {}
    for ref, tail in refs:
        parts = tail.split('.')
        if parts[0] == 'pref':
            key = ('pref', 1)
        elif len(parts) >= 2 and parts[1].isdigit():
            key = (parts[0], int(parts[1]))
        else:
            continue    # book-prologue units (N.pr.*) have no Watson text
        if key in english:
            mapping[ref] = english[key]
    return emit(out, 'la/justin.epitome', refs, lat, mapping, {
        'sources': [{'translator': 'John Selby Watson', 'year': 1853,
                     'title': 'Justin: Epitome of the Philippic History of '
                              'Pompeius Trogus (Bohn)',
                     'publisher': 'H. G. Bohn (attalus.org transcription)',
                     'mode': 'exact', 'ref_composition': ['book', 'chapter'],
                     'source_url': 'http://www.attalus.org/info/justinus.html'}],
        'license': 'Public domain: Watson (Bohn), 1853.',
        'attribution': 'J. S. Watson (Bohn), via attalus.org'})

# --------------------------------------------------- LacusCurtius parsers

def lc_sections(path):
    """{anchor_name: english} from a LacusCurtius English page using
    CLASS="sec"/"chapter" anchors; text runs to the next such anchor."""
    t = open(path, encoding='utf-8', errors='replace').read()
    t = re.sub(r'<A CLASS="ref".*?</A>', ' ', t, flags=re.S | re.I)
    t = re.sub(r'<A[^>]*TARGET="[^"]*"[^>]*>.*?</A>', ' ', t, flags=re.S | re.I)
    t = re.sub(r'<SPAN CLASS="pagenum">.*?</SPAN>', ' ', t, flags=re.S | re.I)
    anchor = re.compile(r'<A CLASS="(?:sec|chapter)" NAME="([0-9.]+)">[^<]*</A>',
                        re.I)
    hits = [(m.start(), m.end(), m.group(1)) for m in anchor.finditer(t)]
    out = {}
    for i, (s, e, name) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(t)
        chunk = t[e:end]
        chunk = re.split(r'<div class="egnote">|Thayer\'s Note', chunk,
                         flags=re.I)[0]
        txt = strip_tags(chunk)
        if len(txt.split()) >= 2:
            # chapter anchors immediately followed by their first sec anchor
            # produce empty chunks, which is fine
            out[name] = txt
    return out


def velleius(src, tess, out):
    english = {}
    for book, pages in (('1', ['velleius_1.html']),
                        ('2', ['velleius_2A.html', 'velleius_2B.html',
                               'velleius_2C.html', 'velleius_2D.html'])):
        for p in pages:
            for name, txt in lc_sections(
                    os.path.join(src, 'velleius', p)).items():
                if '.' in name:
                    ch, sec = name.split('.', 1)
                    english[(book, int(ch), int(sec))] = txt
                else:
                    english.setdefault((book, int(name), 1), txt)
    refs, lat = tess_refs(tess, 'vell. hist.')
    mapping = {}
    for ref, tail in refs:
        p = tail.split('.')
        if len(p) == 3:
            key = (p[0], int(p[1]), int(p[2]))
            if key in english:
                mapping[ref] = english[key]
            else:
                # fall back to the chapter's first section for chapters LC
                # renders as one block
                k2 = (p[0], int(p[1]), 1)
                if k2 in english and int(p[2]) == 1:
                    mapping[ref] = english[k2]
    return emit(out, 'la/velleius_paterculus.historiae_romanae', refs, lat,
                mapping, {
        'sources': [{'translator': 'Frederick W. Shipley', 'year': 1924,
                     'title': 'Velleius Paterculus: Compendium of Roman '
                              'History (Loeb)',
                     'publisher': 'Heinemann (LacusCurtius transcription)',
                     'mode': 'exact',
                     'ref_composition': ['book', 'chapter', 'section'],
                     'source_url': 'https://penelope.uchicago.edu/Thayer/E/'
                                   'Roman/Texts/Velleius_Paterculus/home.html'}],
        'license': 'Public domain: Shipley (Loeb), first printed 1924.',
        'attribution': 'F. W. Shipley (Loeb 1924), via LacusCurtius'})


def strat(src, tess, out):
    english = {}
    for book in '1234':
        secs = lc_sections(os.path.join(src, 'frontinus',
                                        f'strategemata_{book}.html'))
        for name, txt in secs.items():
            if '.' in name:
                ch, ex = name.split('.', 1)
                english[(book, int(ch), int(ex))] = txt
    refs, lat = tess_refs(tess, 'frontin. strat.')
    mapping = {}
    for ref, tail in refs:
        p = tail.split('.')
        if not (len(p) == 3 and p[1].isdigit() and p[2].isdigit()):
            continue        # book prefaces (N.pr.*) are unnumbered in Bennett
        key = (p[0], int(p[1]), int(p[2]))
        if key in english:
            mapping[ref] = english[key]
        elif p[2] == '0':
            # chapter rubric: serve the chapter's first exemplum
            k2 = (p[0], int(p[1]), 1)
            if k2 in english:
                mapping[ref] = english[k2]
    return emit(out, 'la/frontinus.strategemata', refs, lat, mapping, {
        'sources': [{'translator': 'Charles E. Bennett', 'year': 1925,
                     'title': 'Frontinus: The Stratagems (Loeb)',
                     'publisher': 'Heinemann (LacusCurtius transcription)',
                     'mode': 'exact',
                     'ref_composition': ['book', 'chapter', 'exemplum'],
                     'source_url': 'https://penelope.uchicago.edu/Thayer/E/'
                                   'Roman/Texts/Frontinus/Strategemata/home.html'}],
        'license': 'Public domain: Bennett (Loeb), first printed 1925.',
        'attribution': 'C. E. Bennett (Loeb 1925), via LacusCurtius'})


def aquis(src, tess, out):
    english = {}
    for p in ('de_aquis_bennett_1.html', 'de_aquis_bennett_2.html'):
        for name, txt in lc_sections(os.path.join(src, 'frontinus', p)).items():
            # LC anchors are book.section with the CONTINUOUS section second
            n = name.split('.')[-1]
            english.setdefault(int(n), txt)
    refs, lat = tess_refs(tess, 'frontin. aq.')
    mapping = {}
    for ref, tail in refs:
        p = tail.split('.')
        sec = int(p[-1])
        if sec in english:
            mapping[ref] = english[sec]
    return emit(out, 'la/frontinus.de_aquis', refs, lat, mapping, {
        'sources': [{'translator': 'Charles E. Bennett', 'year': 1925,
                     'title': 'Frontinus: The Aqueducts of Rome (Loeb)',
                     'publisher': 'Heinemann (LacusCurtius transcription)',
                     'mode': 'exact', 'ref_composition': ['section'],
                     'source_url': 'https://penelope.uchicago.edu/Thayer/E/'
                                   'Roman/Texts/Frontinus/De_Aquis/home.html'}],
        'license': 'Public domain: Bennett (Loeb), first printed 1925.',
        'attribution': 'C. E. Bennett (Loeb 1925), via LacusCurtius'})

# --------------------------------------------------------------- sidonius

ROMAN_VAL = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}


def roman_to_int(s):
    total, prev = 0, 0
    for ch in reversed(s.strip('. ').upper()):
        v = ROMAN_VAL.get(ch)
        if v is None:
            return None
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total or None


def sidonius(src, tess, out):
    english = {}
    for book in range(1, 10):
        path = os.path.join(src, 'sidonius',
                            f'sidonius_letters_0{book}book{book}.htm')
        t = open(path, encoding='utf-8', errors='replace').read()
        t = re.sub(r'<!--.*?-->', ' ', t, flags=re.S)
        # letters anchor as <A NAME="C7">, sections as <A NAME="7_2">[2]
        hits = [(m.start(), 'L', int(m.group(1)))
                for m in re.finditer(r'<A NAME="C(\d+)">', t)]
        hits += [(m.start(), 'S', (int(m.group(1)), int(m.group(2))))
                 for m in re.finditer(r'<A NAME="(\d+)_(\d+)">', t)]
        hits.sort()
        for i, (pos, kind, val) in enumerate(hits):
            if kind != 'S':
                continue
            end = hits[i + 1][0] if i + 1 < len(hits) else len(t)
            chunk = t[pos:end]
            chunk = re.split(r'<hr|Footnotes|\[Selected footnotes',
                             chunk, flags=re.I)[0]
            txt = strip_tags(chunk)
            txt = re.sub(r'^\[\d+\]\s*', '', txt)
            txt = re.sub(r'\|?\d*\s*\[\d+\]', ' ', txt)   # footnote refs
            txt = re.sub(r'\s+', ' ', txt).strip()
            if len(txt.split()) >= 3:
                english[(book,) + val] = txt
    refs, lat = tess_refs(tess, 'sidon. epist.')
    mapping = {}
    for ref, tail in refs:
        p = tail.split('.')
        if len(p) != 3 or not p[2].isdigit():
            continue
        b, l, s_ = int(p[0]), int(p[1]), int(p[2])
        if s_ == 0:
            # salutation: serve the letter's first section
            key = (b, l, 1)
        else:
            key = (b, l, s_)
        if key in english:
            mapping[ref] = english[key]
    return emit(out, 'la/sidonius.epistulae', refs, lat, mapping, {
        'sources': [{'translator': 'O. M. Dalton', 'year': 1915,
                     'title': 'The Letters of Sidonius (2 vols)',
                     'publisher': 'Clarendon Press '
                                  '(tertullian.org transcription)',
                     'mode': 'exact',
                     'ref_composition': ['book', 'letter', 'section'],
                     'source_url': 'https://www.tertullian.org/fathers/'
                                   'sidonius_letters_00_0_epreface.htm'}],
        'license': 'Public domain: Dalton, 1915. Transcription by Roger '
                   'Pearse (public domain).',
        'attribution': 'O. M. Dalton (1915), via tertullian.org'})


# ---------------------------------------------------------- gregory regula

def gregory_regula(src, tess, out):
    t = open(os.path.join(src, 'gregory', 'npnf212.txt'), encoding='utf-8',
             errors='replace').read()
    parts = list(re.finditer(r'^\s*Part ([IVX]+)\.?\s*$', t, flags=re.M))
    english = {}
    for pi, pm in enumerate(parts):
        pnum = roman_to_int(pm.group(1))
        end = parts[pi + 1].start() if pi + 1 < len(parts) else \
            t.find('THE BOOK OF THE EPISTLES', pm.end())
        if end < 0:
            end = pm.end() + 300000
        seg = t[pm.end():end]
        chapters = list(re.finditer(
            r'^\s*(Prologue|Chapter [IVXL]+)\.?\s*$', seg, flags=re.M))
        for ci, cm in enumerate(chapters):
            cend = chapters[ci + 1].start() if ci + 1 < len(chapters) else len(seg)
            body = seg[cm.end():cend]
            body = re.sub(r'_{5,}', ' ', body)
            body = re.sub(r'\[\d+\]', ' ', body)         # footnote refs
            body = re.sub(r'\s+', ' ', body).strip()
            if cm.group(1) == 'Prologue':
                key = 'pr'
            else:
                key = str(roman_to_int(cm.group(1).split()[1]))
            if len(body.split()) >= 10:
                english[(pnum, key)] = body
        # text between the Part heading and the first chapter = part prologue
        if chapters and (pnum, 'pr') not in english:
            head = seg[:chapters[0].start()]
            head = re.sub(r'_{5,}', ' ', head)
            head = re.sub(r'\[\d+\]', ' ', head)
            head = re.sub(r'\s+', ' ', head).strip()
            if len(head.split()) >= 20:
                english[(pnum, 'pr')] = head
    refs, lat = tess_refs(tess, 'greg. reg_past.')
    mapping = {}
    for ref, tail in refs:
        p = tail.split('.')
        part, ch = int(p[0]), p[1]
        if part == 3:
            # corpus numbers Part III's prologue as chapter 1
            key = (3, 'pr') if ch == '1' else (3, str(int(ch) - 1))
        else:
            key = (part, ch)
        if key in english:
            mapping[ref] = english[key]
    return emit(out, 'la/gregorius_magnus.regula_pastoralis', refs, lat,
                mapping, {
        'sources': [{'translator': 'James Barmby', 'year': 1895,
                     'title': 'The Book of Pastoral Rule (NPNF ser. 2 vol. 12)',
                     'publisher': 'Christian Literature Company '
                                  '(CCEL transcription)',
                     'mode': 'exact',
                     'ref_composition': ['part', 'chapter'],
                     'source_url': 'https://www.ccel.org/ccel/schaff/npnf212'}],
        'license': 'Public domain: NPNF series 2 vol. 12 (1895).',
        'attribution': 'J. Barmby (NPNF 2.12), via CCEL'})


# ------------------------------------------------------ abelard historia

def proportional_blocks(refs_in_ch, english, block=6):
    """Assign English to blocks of corpus sentences by character share."""
    out = {}
    n = len(refs_in_ch)
    if n == 0 or not english:
        return out
    blocks = [refs_in_ch[i:i + block] for i in range(0, n, block)]
    lat_lens = [sum(len(l) for _r, l in b) for b in blocks]
    total = sum(lat_lens) or 1
    # split english at sentence boundaries proportionally
    sents = re.split(r'(?<=[.!?])\s+', english)
    sent_lens = [len(x) for x in sents]
    etotal = sum(sent_lens) or 1
    si = 0
    acc = 0.0
    for bi, b in enumerate(blocks):
        share = lat_lens[bi] / total
        target = share * etotal
        taken, tlen = [], 0
        while si < len(sents) and (tlen < target or not taken):
            taken.append(sents[si])
            tlen += sent_lens[si]
            si += 1
        if bi == len(blocks) - 1 and si < len(sents):
            taken.extend(sents[si:])
            si = len(sents)
        txt = ' '.join(taken).strip()
        for r, _l in b:
            out[r] = txt
    return out


def abelard_hist(src, tess, out):
    t = open(os.path.join(src, 'abelard',
                          'pg14268_bellows_historia_calamitatum.txt'),
             encoding='utf-8', errors='replace').read()
    marks = list(re.finditer(r'^\s*(CHAPTER [IVXL]+|FOREWORD)\s*$', t,
                             flags=re.M))
    bodies = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else \
            t.find('*** END OF')
        body = t[m.end():end]
        body = re.sub(r'^[A-Z0-9 ,;:\'\u2019&#8212;\-]+$', ' ', body, flags=re.M)  # title lines
        body = re.sub(r'\s+', ' ', body).strip()
        bodies.append(body)
    # corpus (Migne) 2 -> FOREWORD; 3-6 -> I-IV; 6 also gets V (Bellows
    # splits Migne's ch. 6); 7-16 -> VI-XV
    chap_eng = {2: bodies[0]}
    for ch in range(3, 6):
        chap_eng[ch] = bodies[ch - 2]
    chap_eng[6] = bodies[4] + ' ' + bodies[5]
    for ch in range(7, 17):
        chap_eng[ch] = bodies[ch - 1]
    refs, lat = tess_refs(tess, 'abael. hist.')
    by_ch = {}
    for ref, tail in refs:
        ch = int(tail.split('.')[0])
        by_ch.setdefault(ch, []).append((ref, lat[ref]))
    mapping = {}
    for ch, rows in by_ch.items():
        mapping.update(proportional_blocks(rows, chap_eng.get(ch, '')))
    return emit(out, 'la/abelard.historia_calamitatum', refs, lat, mapping, {
        'sources': [{'translator': 'Henry Adams Bellows', 'year': 1922,
                     'title': 'Historia Calamitatum: The Story of My '
                              'Misfortunes',
                     'publisher': 'T. A. Boyd (Project Gutenberg #14268)',
                     'mode': 'chapter-proportional',
                     'ref_composition': ['chapter'],
                     'source_url': 'https://www.gutenberg.org/ebooks/14268'}],
        'license': 'Public domain: Bellows, 1922.',
        'attribution': 'H. A. Bellows (1922), via Project Gutenberg'})


WORKS = {'justin': justin, 'velleius': velleius, 'strat': strat,
         'aquis': aquis, 'sidonius': sidonius,
         'gregory_regula': gregory_regula, 'abelard_hist': abelard_hist}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True, choices=sorted(WORKS))
    ap.add_argument('--src', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    ok = WORKS[args.work](args.src, args.tess, args.out)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
