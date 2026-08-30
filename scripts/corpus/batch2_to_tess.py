#!/usr/bin/env python3
"""Convert Latin corpus batch 2 sources to Tesserae .tess files.

Second Latin import batch (2026-08-30): Fronto, Nemesianus (+pseudo De
Aucupio), Symmachus, Abelard, Gregory the Great. Pseudo-Quintilian's
Declamationes Minores are handled by ritter_declmin_to_tess.py (OCR
consensus pipeline), not here. Sources (downloaded pages in --src):

  fronto.epistulae            The Latin Library fronto.html (George Hinge
                              transcription; per-letter anchors mcaes_1_1
                              etc., numbered sections in <sup>)
  nemesianus.eclogae          Latin Library nemesianus1-4.html
  nemesianus.cynegetica       LacusCurtius Latin page (Duff Loeb text)
  nemesianus_pseudo.de_aucupio LacusCurtius Latin page, 2 fragments
  symmachus.epistulae         la.wikisource Libri Decem Epistolarum
                              (Patrologia Latina 18), books I-X wikitext
  abelard.historia_calamitatum monumenta.ch Petrus Abaelardus, Epistolae
                              p1 (Migne PL 178 text; 16 chapters,
                              numbered sentences)
  abelard.epistolae           monumenta.ch, Epistolae p2-p8 (the Heloise
                              correspondence)
  gregorius_magnus.dialogi    monumenta.ch, Dialogi books 1-4 (numbered
                              sentences; ch 0 = prologue; the facing
                              Greek of Zacharias is dropped)
  gregorius_magnus.regula_pastoralis monumenta.ch, Regula pastoralis
                              parts 1-4

Reference schemes (stable, matching citation structure):
  fronto.epistulae            front. epist. <coll>.<letter>.<section>
                              (coll = mcaes1-5, antimp1..., verimp1...,
                              amic1-2, antpium, eloq1-5, orat, addit;
                              .0 = salutation)
  nemesianus.eclogae          nemes. ecl. poem.line
  nemesianus.cynegetica       nemes. cyn. line
  nemesianus_pseudo.de_aucupio nemes_ps. aucup. fragment.line
  symmachus.epistulae         symm. epist. book.letter.par
                              (.0 = salutation; PL numbering, which
                              differs in places from Seeck's MGH)
  abelard.historia_calamitatum abael. hist. chapter.sentence
  abelard.epistolae           abael. epist. letter.chapter.sentence
                              (letters numbered 2-8, Migne order)
  gregorius_magnus.dialogi    greg. dial. book.chapter.sentence (pr = prologue)
  gregorius_magnus.regula_pastoralis greg. reg_past. part.chapter.sentence

Usage: batch2_to_tess.py --src <dir> --out <dir> [--only work ...]
"""
import argparse
import glob
import html as html_mod
import os
import re

# ---------------------------------------------------------------- helpers

def read(path):
    return open(path, encoding='utf-8', errors='replace').read()


def strip_tags(s):
    s = re.sub(r'<script.*?</script>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html_mod.unescape(s)
    s = re.sub(r'[⁠​‎­﻿]', '', s)  # zero-width/joiners
    return re.sub(r'\s+', ' ', s).strip()


def write_tess(out_dir, name, units):
    path = os.path.join(out_dir, name + '.tess')
    n = 0
    with open(path, 'w', encoding='utf-8') as fh:
        for ref, text in units:
            text = re.sub(r'\s+', ' ', text).strip()
            if not text:
                continue
            fh.write(f'<{ref}>\t{text}\n')
            n += 1
    print(f'  {name}: {n} lines')
    return n


def split_paragraphs(text, target=900):
    """Split long prose into ~target-char units at sentence boundaries."""
    sents = re.split(r'(?<=[.!?])\s+', text)
    units, cur = [], ''
    for s in sents:
        if cur and len(cur) + len(s) + 1 > target:
            units.append(cur.strip())
            cur = s
        else:
            cur = f'{cur} {s}'.strip()
    if cur.strip():
        units.append(cur.strip())
    return units

# ---------------------------------------------------------------- fronto

FRONTO_COLL = {
    'mcaes': 'mcaes', 'antimp': 'antimp', 'verimp': 'verimp',
    'amic': 'amic', 'antpium': 'antpium', 'addit': 'addit',
    'de_eloqu': 'eloq', 'de_orat': 'orat',
}


def fronto(src, out):
    t = read(os.path.join(src, 'fronto', 'll_fronto_epistulae.html'))
    anchor = re.compile(
        r'<a[^>]*name="(mcaes|antimp|verimp|amic|antpium|addit|de_eloqu|de_orat)'
        r'(?:_(\d+))?(?:_(\d+))?"[^>]*>')
    hits = [(m.start(), m.group(1), m.group(2), m.group(3))
            for m in anchor.finditer(t)]
    units = []
    for idx, (pos, coll, a, b) in enumerate(hits):
        # letter anchors: coll_book_letter for the book collections,
        # coll_letter for the flat ones; everything else is a heading/TOC
        end_pos = hits[idx + 1][0] if idx + 1 < len(hits) else len(t)
        body = t[pos:end_pos]
        if coll in ('mcaes', 'antimp', 'verimp', 'amic'):
            if b is not None:
                colltag, letter = f'{FRONTO_COLL[coll]}{a}', int(b)
            elif 'Hout' in body:
                # a letter with no anchor of its own directly under a book
                # heading (ad Verum Imp. 2 [118 Hout])
                m = re.search(r'<u>[^<]*?(\d+)\s*\[[^]]*Hout', body)
                colltag = f'{FRONTO_COLL[coll]}{a}'
                letter = int(m.group(1)) if m else 1
            else:
                continue
        else:
            if a is not None and b is None:
                colltag, letter = FRONTO_COLL[coll], int(a)
            elif a is None and 'Hout' in body:
                colltag, letter = FRONTO_COLL[coll], 1  # single-piece work
            else:
                continue
        # The Latin Library leaves many <p> unclosed: split on openings
        # rather than requiring </p> pairs
        paras = re.split(r'<p[^>]*>', body)[1:]
        paras = [re.sub(r'</p>.*', '', p, flags=re.S) for p in paras]
        paras = [p for p in paras if strip_tags(p) not in ('', '\xa0')]
        # drop letter-title lines ('ad Verum Imp. 2 [118 Hout; 2.128 Haines]')
        paras = [p for p in paras if not re.search(r'\[[^]]*Hout', p)]
        if not paras:
            continue

        def clean(x):
            x = strip_tags(x)
            x = x.replace('<', '').replace('>', '')   # editorial brackets
            x = re.sub(r'The Latin Library|The Classics Page', '', x)
            return re.sub(r'\s+', ' ', x).strip()

        # salutation: first para without a section marker
        rest = paras
        if paras and '<sup>' not in paras[0]:
            sal = clean(paras[0])
            if sal:
                units.append((f'front. epist. {colltag}.{letter}.0', sal))
            rest = paras[1:]
        flow = ' '.join(rest)
        pieces = re.split(r'<sup>(\d+)</sup>', flow)
        pre = clean(pieces[0]) if pieces[0].strip() else ''
        marked = list(zip(pieces[1::2], pieces[2::2]))
        if pre and marked:
            # unmarked fragment before section 1 belongs with section 1
            marked[0] = (marked[0][0], pre + ' ' + marked[0][1])
        elif pre:
            units.append((f'front. epist. {colltag}.{letter}.1', pre))
        for num, chunk in marked:
            txt = clean(chunk)
            if txt:
                units.append((f'front. epist. {colltag}.{letter}.{int(num)}',
                              txt))
    return write_tess(out, 'fronto.epistulae', units)


# ------------------------------------------------------------- nemesianus

def nemesianus(src, out):
    total = 0
    units = []
    for poem in range(1, 5):
        t = read(os.path.join(src, 'nemesianus', f'll_ecloga{poem}.html'))
        body = t[t.find('class=pagehead'):]
        lines = []
        for para in re.findall(r'<p[^>]*>(.*?)</p>', body, flags=re.S | re.I):
            for piece in re.split(r'<br\s*/?>', para, flags=re.I):
                txt = strip_tags(piece)
                if txt and not txt.isupper() and 'Latin Library' not in txt \
                        and 'Classics Page' not in txt and 'NEMESIANUS' not in txt:
                    lines.append(txt)
        for i, ln in enumerate(lines, 1):
            units.append((f'nemes. ecl. {poem}.{i}', ln))
    total += write_tess(out, 'nemesianus.eclogae', units)

    for fname, work, ab in (('lc_cynegetica_latin.html', 'nemesianus.cynegetica',
                             'nemes. cyn.'),
                            ('lc_de_aucupio_latin.html',
                             'nemesianus_pseudo.de_aucupio', 'nemes_ps. aucup.')):
        t = read(os.path.join(src, 'nemesianus', fname))
        t = re.sub(r'<A CLASS="translation_flag".*?</A>', ' ', t,
                   flags=re.S | re.I)
        t = re.sub(r'<A CLASS="ref".*?</A>', ' ', t, flags=re.S | re.I)
        units = []
        # one <P CLASS="(start)lineN"> per verse line, anchored NAME="n" or
        # NAME="frag.n" (De Aucupio); LacusCurtius page anchors ("p512") and
        # displayed line numbers are noise
        para = re.compile(r'<P CLASS="(?:start)?line\d*"[^>]*>(.*?)'
                          r'(?=<P CLASS|</TD>|</TABLE>)', re.S | re.I)
        for m in para.finditer(t):
            chunk = m.group(1)
            nm = re.search(r'NAME="(\d+)(?:\.(\d+))?"', chunk)
            txt = strip_tags(chunk)
            txt = re.sub(r'\bp\d+\b', ' ', txt)       # page anchors
            txt = re.sub(r'^\s*\d+\s+', '', txt)      # displayed line number
            txt = re.sub(r'\s+\d+\s*$', '', txt)
            txt = re.sub(r'\s+', ' ', txt).strip()
            if not txt or not nm:
                continue
            if nm.group(2):
                units.append((f'{ab} {int(nm.group(1))}.{int(nm.group(2))}', txt))
            else:
                units.append((f'{ab} {int(nm.group(1))}', txt))
        total += write_tess(out, work, units)
    return total

# -------------------------------------------------------------- symmachus

ROMAN = {'PRIMA': 1, 'SECUNDA': 2, 'TERTIA': 3, 'QUARTA': 4, 'QUINTA': 5}


def roman_to_int(s):
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        v = vals.get(ch)
        if v is None:
            return None
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


def symmachus(src, out):
    units = []
    files = sorted(glob.glob(os.path.join(src, 'symmachus',
                                          'ws_epistulae_liber_*.txt')))
    for bk, path in enumerate(files, 1):
        w = read(path)
        w = html_mod.unescape(w).replace('\xa0', ' ')
        w = re.sub(r'\{\{[^}]*\}\}', '', w, flags=re.S)   # templates
        w = re.sub(r'\[\[(?:[^]|]*\|)?([^]]*)\]\]', r'\1', w)  # links
        parts = re.split(r'==+\s*EPIST[^=]*==+|==+\s*EPISTOLA[^=]*==+', w)
        heads = re.findall(r'==+\s*(EPIST[^=]*?|EPISTOLA[^=]*?)\s*==+', w)
        assert len(parts) == len(heads) + 1, f'book {bk}: split mismatch'
        for n, body in enumerate(parts[1:], 1):
            body = body.strip()
            if not body:
                continue
            lines = [l.strip() for l in body.split('\n')]
            text = re.sub(r'\s+', ' ', ' '.join(lines)).strip()
            # salutation: leading ALL-CAPS run ending before first lowercase
            m = re.match(r"([A-Z][A-Z .,':;]{5,120}?\.)\s+(?=[A-Z][a-z]|[A-Z]{2})",
                         text)
            sal = ''
            if m and not re.search(r'[a-z]', m.group(1)):
                sal = m.group(1).strip()
                text = text[m.end():].strip()
            if sal:
                units.append((f'symm. epist. {bk}.{n}.0', sal))
            for i, para in enumerate(split_paragraphs(text), 1):
                units.append((f'symm. epist. {bk}.{n}.{i}', para))
    return write_tess(out, 'symmachus.epistulae', units)

# ------------------------------------------------------ monumenta parser

def monumenta_units(path, id_prefix):
    """[(id_tuple, sentence_text)] from a monumenta.ch text page.

    Sentences are anchored by <a name=N class="satznummer" href="...id=<full
    id>&..."> and run to the next satznummer anchor or table cell close.
    Manuscript-image links (bildlink) contribute sigla, not text: removed.
    Greek parallel text (greek2 spans, and ids whose chapter token ends G)
    is dropped.
    """
    t = read(path)
    t = re.sub(r'<span class="greek2">.*?</span>', ' ', t, flags=re.S)
    t = re.sub(r'<a class="bildlink".*?</a>', ' ', t, flags=re.S)
    t = re.sub(r'<a class="(?:back_forth|session_trace)".*?</a>', ' ', t,
               flags=re.S)
    anchor = re.compile(r'<a name="\d+" class="satznummer" '
                        r'href="a\.php\?[^"]*?id=([^&"]*)&[^"]*"[^>]*>\d+</a>')
    hits = [(m.start(), m.end(), m.group(1)) for m in anchor.finditer(t)]
    out = []
    for i, (s, e, sid) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(t)
        txt = strip_tags(t[e:end])
        # malformed nav-arrow entities ('&gt;&gt&gt;') survive unescaping
        txt = re.sub(r'\s*[<>]+\s*', ' ', txt).strip()
        parts = tuple(p.strip() for p in sid.split(','))
        if not parts[0].startswith(id_prefix):
            continue
        out.append((parts, txt))
    return out


def abelard(src, out):
    total = 0
    # historia = Epistolae p1: id (Petrus Abaelardus, Epistolae, p1, pCH, N)
    units = []
    for parts, txt in monumenta_units(
            os.path.join(src, 'abelard', 'mon_epistola_p1.html'), 'Petrus'):
        if len(parts) != 5:
            continue
        ch = parts[3].lstrip('p')
        n = parts[4]
        if int(ch) == 1:
            continue        # Migne's editorial argumentum, not Abelard
        units.append((f'abael. hist. {int(ch)}.{int(n)}', txt))
    total += write_tess(out, 'abelard.historia_calamitatum', units)

    units = []
    for ep in range(2, 9):
        rows = monumenta_units(
            os.path.join(src, 'abelard', f'mon_epistola_p{ep}.html'), 'Petrus')
        for parts, txt in rows:
            if len(parts) == 5:
                ch, n = parts[3].lstrip('p'), parts[4]
                if int(ch) == 1:
                    continue    # Migne's editorial argumentum, not the letter
                units.append((f'abael. epist. {ep}.{int(ch)}.{int(n)}', txt))
            elif len(parts) == 4:
                units.append((f'abael. epist. {ep}.1.{int(parts[3])}', txt))
    total += write_tess(out, 'abelard.epistolae', units)
    return total


def gregory(src, out):
    total = 0
    units = []
    for bk in range(1, 5):
        for parts, txt in monumenta_units(
                os.path.join(src, 'gregory', f'mon_dialogi_liber{bk}.html'),
                'Gregorius'):
            # (Gregorius Magnus, Dialogi, book, chapter, sentence)
            if len(parts) != 5:
                continue
            ch = parts[3]
            if ch.endswith('G'):
                continue                       # Greek parallel
            ch = ch.rstrip('L')
            ch = 'pr' if ch in ('0', '') else str(int(ch))
            units.append((f'greg. dial. {bk}.{ch}.{int(parts[4])}', txt))
    total += write_tess(out, 'gregorius_magnus.dialogi', units)

    units = []
    for p in range(1, 5):
        for parts, txt in monumenta_units(
                os.path.join(src, 'gregory', f'mon_regula_pastoralis_p{p}.html'),
                'Gregorius'):
            if len(parts) == 5:
                ch = parts[3].lstrip('p').rstrip('L')
                ch = 'pr' if ch in ('0', '') else str(int(ch))
                units.append((f'greg. reg_past. {p}.{ch}.{int(parts[4])}', txt))
            elif len(parts) == 4:
                units.append((f'greg. reg_past. {p}.1.{int(parts[3])}', txt))
    total += write_tess(out, 'gregorius_magnus.regula_pastoralis', units)
    return total


WORKS = {
    'fronto': fronto,
    'nemesianus': nemesianus,
    'symmachus': symmachus,
    'abelard': abelard,
    'gregory': gregory,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--only', nargs='*')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for name, fn in WORKS.items():
        if args.only and name not in args.only:
            continue
        fn(args.src, args.out)


if __name__ == '__main__':
    main()
