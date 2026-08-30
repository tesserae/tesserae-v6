#!/usr/bin/env python3
"""Convert Latin corpus batch 3 sources to Tesserae .tess files:
Aquinas (Summa Theologiae Prima Pars + the Corpus Christi hymns) and
Erasmus (Moriae Encomium + selected Colloquia familiaria).

Sources (downloaded pages in --src):
  aquinas.summa_theologiae_1   Corpus Thomisticum sth1*.html (Ia qq. 1-119)
  aquinas.hymni                the five eucharistic hymns (clean transcriptions)
  erasmus.moriae_encomium      The Latin Library erasmus/moriae.shtml
  erasmus.colloquia            selected colloquies (per-colloquy sources)

Reference schemes:
  aquinas.summa_theologiae_1   aquin. sth1a. question.article.paragraph
                               (paragraphs in Corpus Thomisticum's own order:
                               arg 1..n, s.c., co., ad 1..n; question
                               prologues are Q.0.P)
  aquinas.hymni                aquin. hymn. poem.line (1 Pange lingua,
                               2 Lauda Sion, 3 Sacris solemniis, 4 Verbum
                               supernum, 5 Adoro te devote)
  erasmus.moriae_encomium      erasm. moria. paragraph.section (paragraphs
                               as printed in the source; long paragraphs
                               split at sentence boundaries ~900 chars;
                               the prefatory letter to More = pr.N)
  erasmus.colloquia            erasm. colloq. n.paragraph (colloquy order
                               recorded in text_sources.json)

Usage: batch3_to_tess.py --src <dir> --out <dir> [--only work ...]
"""
import argparse
import glob
import html as html_mod
import os
import re

def read(path):
    return open(path, encoding='utf-8', errors='replace').read()


def strip_tags(s):
    s = re.sub(r'<script.*?</script>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html_mod.unescape(s)
    s = re.sub(r'[⁠​‎­﻿]', '', s)
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

# ------------------------------------------------------------------ moria

def moria(src, out):
    t = read(os.path.join(src, 'erasmus', 'moriae_latinlibrary.html'))
    paras = [strip_tags(p) for p in
             re.findall(r'<p[^>]*>(.*?)</p>', t, flags=re.S | re.I)]
    paras = [p for p in paras if p and 'The Latin Library' not in p
             and 'Classics Page' not in p and 'The Praise of Folly' not in p]
    body_start = None
    for i, p in enumerate(paras):
        if p.startswith('Ex Rure'):
            body_start = i + 1
            break
    assert body_start, 'no epistle end found'
    units = []
    pr = 0
    for p in paras[1:body_start]:       # the letter to More (title para skipped)
        if p.isupper() or 'MORIAE ENCOMIVM' in p:
            continue
        for chunk in split_paragraphs(p):
            pr += 1
            units.append((f'erasm. moria. pr.{pr}', chunk))
    # body: the source numbers the standard 68 sections at paragraph heads
    # ('12. ' or bare '2 '); one marker (19) is lost and healed by position
    # (its paragraph sits alone between sections 18 and 20)
    marked = []
    for p in paras[body_start:]:
        if p.isupper() or 'MORIAE ENCOMIVM' in p or p.strip() in ('FINIS',
                                                                  'Telos.'):
            continue
        m = re.match(r'^(\d+)\.?\s+(.*)$', p)
        marked.append((int(m.group(1)) if m else None,
                       m.group(2) if m else p))
    sections = []
    cur = 0
    for i, (n, txt) in enumerate(marked):
        if n is not None:
            cur = n
            sections.append((cur, [txt]))
        else:
            nxt = next((m2 for m2, _t in marked[i + 1:] if m2 is not None),
                       None)
            if nxt is not None and nxt == cur + 2:
                cur += 1                     # healed lost marker
                # the lost marker may survive as a mangled token ('I9.')
                txt = re.sub(r'^[Il]\d\.?\s+', '', txt)
                sections.append((cur, [txt]))
            elif sections:
                sections[-1][1].append(txt)
            else:
                sections.append((0, [txt]))  # 'Stultitia loquitur' heading
    seen = set()
    for n, chunks in sections:
        assert n not in seen, f'duplicate section {n}'
        seen.add(n)
        k = 0
        for chunk_text in chunks:
            for piece in split_paragraphs(chunk_text):
                k += 1
                units.append((f'erasm. moria. {n}.{k}', piece))
    assert seen >= set(range(1, 69)), sorted(set(range(1, 69)) - seen)
    return write_tess(out, 'erasmus.moriae_encomium', units)



# ---------------------------------------------------------------- aquinas

CT_REF_RE = re.compile(
    r'^I(?:ª|&ordf;|a)? q\. (\d+)(?: a\. (\d+))? (pr\.|arg\. \d+|s\. c\.|'
    r'co\.|ad \d+|ad arg\.|.*)$')


def parse_ct(src):
    """[(q, a, label, text)] in document order from the Corpus Thomisticum
    sth1*.html pages (a = 0 for question prologues)."""
    rows = []
    for path in sorted(glob.glob(os.path.join(src, 'aquinas', 'summa_latin',
                                              'sth1*.html'))):
        t = open(path, 'rb').read().decode('iso-8859-1')
        for m in re.finditer(r'<P TITLE="([^"]+)">(.*?)</P>', t, flags=re.S):
            title = m.group(1).strip()
            mm = re.match(r'I q\. (\d+)(?: a\. (\d+))?\s*(.*)$', title)
            if not mm:
                continue
            q = int(mm.group(1))
            a = int(mm.group(2)) if mm.group(2) else 0
            label = mm.group(3).strip() or 'pr.'
            body = re.sub(r'<SPAN CLASS="ref">.*?</SPAN>', '', m.group(2),
                          flags=re.S)
            text = strip_tags(body)
            if text:
                rows.append((q, a, label, text))
    return rows


def summa(src, out):
    rows = parse_ct(src)
    qs = {q for q, _a, _l, _t in rows}
    assert qs == set(range(1, 120)), \
        f'Prima Pars coverage broken: missing {sorted(set(range(1,120))-qs)}'
    units = []
    counter = {}
    for q, a, label, text in rows:
        p = counter.get((q, a), 0) + 1
        counter[(q, a)] = p
        units.append((f'aquin. sth1a. {q}.{a}.{p}', text))
    return write_tess(out, 'aquinas.summa_theologiae_1', units)


HYMNS = [
    (1, 'pange_lingua.wiki.txt', 'Pange lingua'),
    (2, 'lauda_sion.wiki.txt', 'Lauda Sion'),
    (3, 'sacris_solemniis.preces-latinae.html', 'Sacris solemniis'),
    (4, 'verbum_supernum.wiki.txt', 'Verbum supernum'),
    (5, 'adoro_te_devote.wiki.txt', 'Adoro te devote'),
]


def hymns(src, out):
    import unicodedata

    def norm(l):
        # strip liturgical accent marks; expand ligatures; drop punctuation-
        # only spacing quirks (': ' with a leading space)
        l = l.replace('\u00e6', 'ae').replace('\u00c6', 'Ae')
        l = l.replace('\u0153', 'oe').replace('\u0152', 'Oe')
        l = ''.join(c for c in unicodedata.normalize('NFD', l)
                    if not unicodedata.combining(c))
        l = re.sub(r'\s+([:;,.!?])', r'\1', l)
        return re.sub(r'\s+', ' ', l).strip()

    units = []
    for num, fname, name in HYMNS:
        t = read(os.path.join(src, 'aquinas', 'hymns', fname))
        lines = []
        if fname.endswith('.wiki.txt'):
            m = re.search(r'<poem>(.*?)</poem>', t, flags=re.S)
            if not m:
                m = re.search(r'<div class="?(?:center)?text"?>(.*?)</div>',
                              t, flags=re.S)
            seg = m.group(1) if m else re.sub(r'\{\{[^}]*\}\}', '', t, flags=re.S)
            seg = re.sub(r'\{\{[^}]*\}\}', '', seg, flags=re.S)
            for raw_line in re.split(r'<br\s*/?>|\n', seg):
                txt = strip_tags(raw_line)
                if txt and not txt.startswith(("''", 'Cf.')):
                    lines.append(txt)
        else:
            # preces-latinae: two-column table, Latin in the FIRST cell of
            # each row; the drop-cap splits the first word ('S ACRIS')
            for row in re.findall(r'<TR[^>]*>(.*?)</TR>', t, flags=re.S | re.I):
                cells = re.findall(r'<TD[^>]*>(.*?)</TD>', row,
                                   flags=re.S | re.I)
                if len(cells) != 2:
                    continue     # stanza rows are exactly Latin | English
                for piece in re.split(r'<br\s*/?>', cells[0], flags=re.I):
                    txt = strip_tags(piece)
                    if txt:
                        lines.append(txt)
        n = 0
        # two typos in the Wikisource Lauda Sion transcription, corrected
        # against the received text (caught by the PR auto-review)
        TYPOS = {'sumnt': 'sumunt', 'mettendus': 'mittendus'}
        for l in lines:
            # wiki residue: unwrap [[link|text]] links, drop pure
            # category/interwiki lines
            if re.fullmatch(r'\[\[(?:[A-Za-z-]{2,10}:|Categoria:).*\]\]',
                            l.strip()):
                continue
            l = re.sub(r'\[\[(?:[^]|]*\|)?([^]]*)\]\]', r'\1', l)
            l = norm(l)
            for bad, good in TYPOS.items():
                l = re.sub(r'\b%s\b' % bad, good, l)
            if not l or len(l) < 4 or l.isdigit():
                continue
            if re.match(r'^[A-Z] [A-Z]+', l):     # drop-cap 'S ACRIS...'
                l = l[0] + l[2:]
            # a drop-cap first word prints ALL CAPS; restore normal case
            l = re.sub(r'^([A-Z])([A-Z]{2,})\b',
                       lambda m: m.group(1) + m.group(2).lower(), l)
            n += 1
            units.append((f'aquin. hymn. {num}.{n}', l))
        print(f'    hymn {num} {name}: {n} lines')
    return write_tess(out, 'aquinas.hymni', units)



# -------------------------------------------------------------- colloquia

COLLOQUIA = [
    (1, 'naufragium', 'Naufragium'),
    (2, 'abbatis_et_eruditae', 'Abbatis et eruditae'),
    (3, 'charon', 'Charon'),
    (4, 'peregrinatio_religionis_ergo', 'Peregrinatio religionis ergo'),
    (5, 'funus', 'Funus'),
    (6, 'convivium_religiosum', 'Convivium religiosum'),
    (7, 'exorcismus_sive_spectrum', 'Exorcismus sive spectrum'),
    (8, 'alcumistica', 'Alcumistica'),
    (9, 'diversoria', 'Diversoria'),
    (10, 'militis_et_carthusiani', 'Militis et Carthusiani'),
    (11, 'proci_et_puellae', 'Proci et puellae'),
    (12, 'coniugium_impar', 'Coniugium impar'),
    (13, 'uxor', 'Uxor mempsigamos'),
    (14, 'puerpera', 'Puerpera'),
    (15, 'adolescentis_et_scorti', 'Adolescentis et scorti'),
    (16, 'cyclops', 'Cyclops sive evangeliophorus'),
    (17, 'inquisitio_de_fide', 'Inquisitio de fide'),
    (18, 'epicureus', 'Epicureus'),
]


def colloquia(src, out):
    units = []
    for num, stem, _name in COLLOQUIA:
        t = read(os.path.join(src, 'erasmus', 'colloquia_la',
                              f'{stem}_wikisource.txt'))
        lines = [l.strip() for l in t.split('\n')]
        # drop the title line and the speaker-list line at the top
        body_lines = []
        started = False
        for l in lines:
            if not started:
                if not l or l.isupper() or l.rstrip('.').isupper():
                    continue
                # speaker list: short line of capitalized names
                if re.fullmatch(r'[A-Z][a-zA-Z]+(?:[.,]\s*[A-Z][a-zA-Z]+)*[.,]?',
                                l) and len(l) < 80:
                    continue
                started = True
            body_lines.append(l)
        # accumulate speaker turns into ~700-char units at turn boundaries
        p = 0
        cur = ''
        for l in body_lines:
            if not l:
                continue
            if cur and len(cur) + len(l) + 1 > 700:
                p += 1
                units.append((f'erasm. colloq. {num}.{p}', cur))
                cur = l
            else:
                cur = f'{cur} {l}'.strip()
        if cur:
            p += 1
            units.append((f'erasm. colloq. {num}.{p}', cur))
        print(f'    colloquy {num} {stem}: {p} units')
    return write_tess(out, 'erasmus.colloquia', units)


WORKS = {'moria': moria, 'summa': summa, 'hymns': hymns,
         'colloquia': colloquia}


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
