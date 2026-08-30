#!/usr/bin/env python3
"""Convert Latin Library HTML pages to Tesserae .tess files.

First Latin corpus import batch (2026-08-30): Varro, Hyginus, Justin,
Velleius Paterculus, Frontinus, Pomponius Mela, Sidonius Apollinaris,
Isidore of Seville. Source pages are downloaded from
https://www.thelatinlibrary.com/ (see MANIFEST below for the exact page
list per work) into a local directory, then converted here. The Latin
Library carries no edition statements for most texts; provenance rows in
backend/text_sources.json record what is known (e.g. Sidonius' carmina
page names Luetjohann's 1887 MGH edition).

Reference schemes (stable, matching each text's citation structure):
  varro.de_lingua_latina        varro. ling.   book.chapter.par
  varro.res_rusticae            varro. rust.   book.chapter.par
  hyginus.astronomica           hyg. astr.     book.chapter.par ('pr' = proem)
  hyginus.fabulae               hyg. fab.      fable.par (.0 = title; fable
                                               numbers are SEQUENTIAL in page
                                               order, not the Rose numbering)
  justin.epitome                iust. epit.    book.chapter (praefatio: pref.1)
  velleius_paterculus.historiae_romanae  vell. hist.  book.chapter.section
                                               (sections from the source's own
                                               inline markers)
  frontinus.strategemata        frontin. strat. book.chapter.exemplum
                                               (.0 = chapter rubric)
  frontinus.de_aquis            frontin. aq.   book.section (source's numbers,
                                               continuous across the work)
  pomponius_mela.de_chorographia mela. chor.   book.section
  sidonius.epistulae            sidon. epist.  book.letter.section
                                               (.0 = salutation)
  sidonius.carmina              sidon. carm.   poem.line
  isidore.etymologiae           isid. orig.    book.chapter.section
                                               (.0 = chapter rubric)

Usage:
  python latinlibrary_to_tess.py --src <dir with downloaded pages> --out <dir>

Downloaded page filenames are the URL path with '/' replaced by '_'
(e.g. frontinus/strat1.shtml -> frontinus_strat1.shtml).
"""
import argparse
import html as html_mod
import os
import re
import sys

MANIFEST = {
    'varro.de_lingua_latina': [f'varro.ll{b}.html' for b in range(5, 11)],
    'varro.res_rusticae': [f'varro.rr{b}.html' for b in range(1, 4)],
    'hyginus.astronomica': [f'hyginus_hyginus{b}.shtml' for b in range(1, 5)],
    'hyginus.fabulae': ['hyginus_hyginus5.shtml'],
    'justin.epitome': ['justin_praefatio.html'] + [f'justin_{b}.html' for b in range(1, 45)],
    'velleius_paterculus.historiae_romanae': ['vell1.html', 'vell2.html'],
    'frontinus.strategemata': [f'frontinus_strat{b}.shtml' for b in range(1, 5)],
    'frontinus.de_aquis': ['frontinus_aqua1.shtml', 'frontinus_aqua2.shtml'],
    'pomponius_mela.de_chorographia': [f'pomponius{b}.html' for b in range(1, 4)],
    'sidonius.epistulae': [f'sidonius{b}.html' for b in range(1, 10)],
    'sidonius.carmina': ['sidoniuscarmina.html'],
    'isidore.etymologiae': [f'isidore_{b}.shtml' for b in range(1, 21)],
}

ABBREV = {
    'varro.de_lingua_latina': 'varro. ling.',
    'varro.res_rusticae': 'varro. rust.',
    'hyginus.astronomica': 'hyg. astr.',
    'hyginus.fabulae': 'hyg. fab.',
    'justin.epitome': 'iust. epit.',
    'velleius_paterculus.historiae_romanae': 'vell. hist.',
    'frontinus.strategemata': 'frontin. strat.',
    'frontinus.de_aquis': 'frontin. aq.',
    'pomponius_mela.de_chorographia': 'mela. chor.',
    'sidonius.epistulae': 'sidon. epist.',
    'sidonius.carmina': 'sidon. carm.',
    'isidore.etymologiae': 'isid. orig.',
}

ROMAN_RE = re.compile(r'^([IVXLCDM]+)\.?$')


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


def read_page(path):
    raw = open(path, 'rb').read()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        text = raw.decode('utf-16')
    else:
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('cp1252', errors='replace')
    # Cut the trailing navigation table (Latin Library footer).
    cut = text.lower().rfind('<table')
    if cut != -1:
        text = text[:cut]
    return text


def paragraphs(page):
    """Yield (attrs, inner_html) for each <p> block."""
    for m in re.finditer(r'(?is)<p([^>]*)>(.*?)(?=<p[^>]*>|\Z)', page):
        yield m.group(1).lower(), m.group(2)


def clean(inner, keep_breaks=False):
    """Strip markup from a paragraph, unescape entities, tidy whitespace."""
    s = re.sub(r'(?is)<br\s*/?>', '\n' if keep_breaks else ' ', inner)
    s = re.sub(r'(?is)<[^>]+>', ' ', s)
    s = html_mod.unescape(s)
    s = s.replace(' ', ' ')
    # editorial supplements arrive as &lt;...&gt;; keep the letters, drop the
    # brackets (they would read as markup residue downstream)
    s = s.replace('<', '').replace('>', '')
    if keep_breaks:
        lines = [re.sub(r'\s+', ' ', ln).strip() for ln in s.split('\n')]
        return '\n'.join(ln for ln in lines if ln)
    return re.sub(r'\s+', ' ', s).strip()


def is_noise(attrs, inner):
    if any(k in attrs for k in ('pagehead', 'border', 'margin', 'footer')):
        return True
    if inner.lower().count('<a href') >= 2:
        return True
    txt = clean(inner)
    if not txt:
        return True
    # pure link/number rows that survived (but a bold roman numeral is a
    # chapter marker, not noise)
    if (re.fullmatch(r'[\dIVXLCDM\s|.\-]+', txt) and len(txt) < 120
            and '<b' not in inner.lower()):
        return True
    return False


def flush(out, abbrev, ref, parts):
    text = re.sub(r'\s+', ' ', ' '.join(parts)).strip()
    if text:
        out.append((f'{abbrev} {ref}', text))


# ---------------------------------------------------------------- handlers

def chapter_bold_prose(page, abbrev, book, out, flat=False):
    """Varro (both works) + Hyginus Astronomica: bold roman-numeral chapter
    markers, sometimes with a rubric and/or running text in the same block.
    With flat=True (De Lingua Latina, which is cited by book.section, not by
    chapter) the markers are skipped and paragraphs numbered per book."""
    chap, par = 'pr', 0
    last_num = 0
    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        m = re.match(r'(?is)\s*(?:<a[^>]*>\s*</a>\s*)?<b>\s*([IVXLCDM]+)\s*\.\s*(.*?)</b>\s*(.*)',
                     inner)
        if m and roman_to_int(m.group(1)) is not None:
            if not flat:
                chap = roman_to_int(m.group(1))
                if chap <= last_num:
                    chap = last_num + 1  # source misprint: keep numbering forward
                last_num = chap
                par = 0
            rubric = clean(m.group(2))
            rest = clean(m.group(3))
            text = ' '.join(t for t in (rubric, rest) if t)
            if text:
                par += 1
                ref = f'{book}.{par}' if flat else f'{book}.{chap}.{par}'
                flush(out, abbrev, ref, [text])
            continue
        par += 1
        ref = f'{book}.{par}' if flat else f'{book}.{chap}.{par}'
        flush(out, abbrev, ref, [clean(inner)])


def fabulae(page, abbrev, out):
    """Hyginus Fabulae: bold all-caps titles delimit fables; numbering is
    sequential in page order."""
    n, par = 0, 0
    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        txt = clean(inner)
        is_title = ('<b>' in inner.lower() and len(txt) < 90
                    and txt == txt.upper() and re.search(r'[A-Z]', txt))
        if is_title:
            n += 1
            par = 0
            flush(out, abbrev, f'{n}.0', [txt])
            continue
        if n == 0:
            continue  # front matter before the first fable
        par += 1
        flush(out, abbrev, f'{n}.{par}', [txt])


def justin(page, abbrev, book, out):
    """Justin: [ROMAN] chapter markers; multi-paragraph chapters merged so the
    ref (book.chapter) stays unique."""
    cur, parts = None, []
    pre = 0
    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        txt = clean(inner)
        if re.fullmatch(r'(?i)liber\s+[IVXLCDM]+\.?|praefatio', txt):
            continue
        m = re.match(r'\[([IVXLCDM]+)\]\s*(.*)', txt, re.S)
        if m and roman_to_int(m.group(1)) is not None:
            if cur is not None:
                flush(out, abbrev, f'{book}.{cur}', parts)
            nxt = roman_to_int(m.group(1))
            if isinstance(cur, int) and nxt <= cur:
                nxt = cur + 1  # source misprint: keep numbering forward
            cur, parts = nxt, [m.group(2)]
        elif cur is not None:
            parts.append(txt)
        else:
            pre += 1
            flush(out, abbrev, f'{book}.{pre}' if book == 'pref' else f'{book}.pr.{pre}', [txt])
    if cur is not None:
        flush(out, abbrev, f'{book}.{cur}', parts)


def velleius(page, abbrev, book, out):
    """Velleius: [<a name>N</a>] chapter markers, <font>N</font> section
    markers inline; text accumulates across paragraph boundaries."""
    stream = []
    for attrs, inner in paragraphs(page):
        if 'pagehead' in attrs or 'border' in attrs or 'margin' in attrs:
            continue
        stream.append(inner)
    joined = ' '.join(stream)
    # tokenized walk: chapter markers and section markers split the stream
    tokens = re.split(r'(?is)(\[\s*<a name="[^"]*">\s*(?:[IVXLCDM]+|\d+)\s*</a>\s*\]'
                      r'|<font[^>]*>\s*\d+\s*</font>)', joined)
    chap, sect, parts = None, 1, []
    for tok in tokens:
        mc = re.match(r'(?is)\[\s*<a name="[^"]*">\s*([IVXLCDM]+|\d+)\s*</a>\s*\]', tok)
        ms = re.match(r'(?is)<font[^>]*>\s*(\d+)\s*</font>', tok)
        if mc:
            if chap is not None:
                flush(out, abbrev, f'{book}.{chap}.{sect}', parts)
            num = mc.group(1)
            num = int(num) if num.isdigit() else roman_to_int(num)
            if chap is not None and num <= int(chap):
                num = int(chap) + 1  # source misprint: keep numbering forward
            chap = str(num)
            sect, parts = 1, []
        elif ms:
            if chap is not None:
                flush(out, abbrev, f'{book}.{chap}.{sect}', parts)
            nxt = int(ms.group(1))
            if nxt <= sect:
                nxt = sect + 1  # source misprint (e.g. 1.14 '5' after '7')
            sect, parts = nxt, []
        else:
            txt = clean(tok)
            if txt:
                if chap is None:
                    continue  # heading noise before the first chapter
                parts.append(txt)
    if chap is not None:
        flush(out, abbrev, f'{book}.{chap}.{sect}', parts)


def strategemata(page, abbrev, book, out):
    """Frontinus Strategemata: centered bold rubrics open chapters; each
    paragraph under a rubric is one exemplum."""
    chap, ex = 'pr', 0
    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        txt = clean(inner)
        if re.fullmatch(r'(?i)liber\s+[a-z]+\.?', txt):
            continue
        is_rubric = ('<b>' in inner.lower() and txt == txt.upper()
                     and len(txt) < 140)
        if is_rubric:
            chap = chap + 1 if isinstance(chap, int) else 1
            ex = 0
            flush(out, abbrev, f'{book}.{chap}.0', [txt])
            continue
        ex += 1
        flush(out, abbrev, f'{book}.{chap}.{ex}', [txt])


def numbered_sections(page, abbrev, book, out, marker):
    """De Aquis ('N. ' prefixes) and Mela ('[N]' prefixes): source-numbered
    sections; unnumbered paragraphs continue the current section."""
    if marker == 'dot':
        rx = re.compile(r'^(\d+)\.\s+(.*)', re.S)
    else:
        rx = re.compile(r'^\[(\d+)\]\s*(.*)', re.S)
    cur, parts = None, []
    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        txt = clean(inner)
        if re.fullmatch(r'(?i)liber\s+[a-z]+\.?', txt):
            continue
        m = rx.match(txt)
        if m:
            if cur is not None:
                flush(out, abbrev, f'{book}.{cur}', parts)
            cur, parts = int(m.group(1)), [m.group(2)]
        elif cur is not None:
            parts.append(txt)
    if cur is not None:
        flush(out, abbrev, f'{book}.{cur}', parts)


def sidonius_ep(page, abbrev, book, out):
    """Sidonius letters: 'EPISTULA N' headings; salutation is section 0;
    'N. ' paragraphs are sections; unnumbered paragraphs continue."""
    letter, sect, parts, started = None, None, [], False
    def emit():
        if letter is not None and sect is not None:
            flush(out, abbrev, f'{book}.{letter}.{sect}', parts)
    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        txt = clean(inner)
        m = re.match(r'(?i)^epistula\s+([IVXLCDM]+)\s*\.?\s*$', txt)
        if m:
            emit()
            letter = roman_to_int(m.group(1))
            sect, parts, started = None, [], False
            continue
        if letter is None:
            continue
        m = re.match(r'^(\d+)\.\s+(.*)', txt, re.S)
        if m:
            emit()
            sect, parts = int(m.group(1)), [m.group(2)]
        elif not started:
            sect, parts = 0, [txt]  # salutation
        else:
            parts.append(txt)
        started = True
    emit()


def sidonius_carm(page, abbrev, out):
    """Sidonius carmina: one page; 'CARMEN N' anchors open poems; verse lines
    separated by <br>; all-caps rubric paragraphs are skipped."""
    poem, line = None, 0
    for attrs, inner in paragraphs(page):
        if any(k in attrs for k in ('pagehead', 'border', 'margin')):
            continue
        header = re.search(r'(?i)CARMEN\s+([IVXLCDM]+)', clean(inner))
        if header and '<b>' in inner.lower():
            poem = roman_to_int(header.group(1))
            line = 0
            continue
        if poem is None:
            continue
        txt = clean(inner, keep_breaks=True)
        if not txt:
            continue
        if txt == txt.upper() and '\n' not in txt and len(txt) < 160:
            continue  # rubric
        for verse in txt.split('\n'):
            line += 1
            flush(out, abbrev, f'{poem}.{line}', [verse])


def isidore(page, abbrev, book, out):
    """Etymologiae: 'ROMAN. RUBRIC.' chapter openings with [N] section
    markers inline; the rubric becomes section 0. Front matter before the
    first chapter (book rubric, proems) goes to chapter 'pr'."""
    chap, sect, parts = None, None, []
    pre = 0
    used = set()

    def emit():
        nonlocal chap
        if chap is not None and sect is not None and parts:
            if f'{chap}.{sect}' in used and isinstance(chap, int):
                # section numbering restarted with no visible rubric: the
                # source lost a chapter heading; open the next chapter
                chap += 1
            used.add(f'{chap}.{sect}')
            flush(out, abbrev, f'{book}.{chap}.{sect}', parts)

    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        txt = clean(inner)
        m = re.match(r'^([IVXLCDM]+)\.\s+(.*)', txt, re.S)
        if m and roman_to_int(m.group(1)) is not None:
            rubric = m.group(2).split('[')[0].strip()
            if rubric and rubric == rubric.upper():
                emit()
                nxt = roman_to_int(m.group(1))
                if isinstance(chap, int) and nxt <= chap:
                    nxt = chap + 1  # source misprint (XXIX for XXXIX etc.)
                chap = nxt
                sect, parts = 0, [rubric]  # rubric line, flushed as .0
                txt = m.group(2)[len(rubric):].strip()
        if chap is None:
            pre += 1
            flush(out, abbrev, f'{book}.pr.{pre}', [txt])
            continue
        pieces = re.split(r'\[(\d+)\]', txt)
        lead = pieces[0].strip()
        if lead:
            if sect is None:
                sect = 0
                parts = []
            parts.append(lead)
        for i in range(1, len(pieces), 2):
            emit()
            sect = int(pieces[i])
            parts = [pieces[i + 1].strip()]
    emit()


def isidore_stream(page, abbrev, book, out):
    """Fallback for the older Etymologiae page style (books 17, 19), where a
    whole book sits in one block: chapters are found anywhere in the text as
    'ROMAN. ALL-CAPS RUBRIC. [1]', sections at the [N] markers."""
    stream = ' '.join(clean(inner) for attrs, inner in paragraphs(page)
                      if not is_noise(attrs, inner))
    chap_rx = re.compile(r"([IVXLCDM]+)\.\s+([A-Z][A-Z\s,.'()\-]*?\.)\s*(?=\[1\]\s)")
    marks = [m for m in chap_rx.finditer(stream) if roman_to_int(m.group(1))]
    pre = stream[:marks[0].start()].strip() if marks else stream.strip()
    if pre:
        flush(out, abbrev, f'{book}.pr.1', [pre])
    last = 0
    for i, m in enumerate(marks):
        chap = roman_to_int(m.group(1))
        if chap <= last:
            chap = last + 1  # source misprint: keep numbering forward
        last = chap
        flush(out, abbrev, f'{book}.{chap}.0', [m.group(2).strip()])
        end = marks[i + 1].start() if i + 1 < len(marks) else len(stream)
        body = stream[m.end():end]
        pieces = re.split(r'\[(\d+)\]', body)
        for j in range(1, len(pieces), 2):
            flush(out, abbrev, f'{book}.{chap}.{pieces[j]}', [pieces[j + 1].strip()])


# ---------------------------------------------------------------- driver

def convert(work, src):
    abbrev = ABBREV[work]
    out = []
    for page_file in MANIFEST[work]:
        path = os.path.join(src, page_file)
        page = read_page(path)
        if work.startswith('varro.de_lingua'):
            book = int(re.search(r'll(\d+)', page_file).group(1))
            chapter_bold_prose(page, abbrev, book, out, flat=True)
        elif work.startswith('varro.res'):
            book = int(re.search(r'rr(\d+)', page_file).group(1))
            chapter_bold_prose(page, abbrev, book, out)
        elif work == 'hyginus.astronomica':
            book = int(re.search(r'hyginus(\d)', page_file).group(1))
            chapter_bold_prose(page, abbrev, book, out)
        elif work == 'hyginus.fabulae':
            fabulae(page, abbrev, out)
        elif work == 'justin.epitome':
            b = re.search(r'justin_(\w+)\.html', page_file).group(1)
            justin(page, abbrev, 'pref' if b == 'praefatio' else int(b), out)
        elif work.startswith('velleius'):
            book = int(re.search(r'vell(\d)', page_file).group(1))
            velleius(page, abbrev, book, out)
        elif work == 'frontinus.strategemata':
            book = int(re.search(r'strat(\d)', page_file).group(1))
            strategemata(page, abbrev, book, out)
        elif work == 'frontinus.de_aquis':
            book = int(re.search(r'aqua(\d)', page_file).group(1))
            numbered_sections(page, abbrev, book, out, 'dot')
        elif work.startswith('pomponius_mela'):
            book = int(re.search(r'pomponius(\d)', page_file).group(1))
            numbered_sections(page, abbrev, book, out, 'bracket')
        elif work == 'sidonius.epistulae':
            book = int(re.search(r'sidonius(\d)', page_file).group(1))
            sidonius_ep(page, abbrev, book, out)
        elif work == 'sidonius.carmina':
            sidonius_carm(page, abbrev, out)
        elif work == 'isidore.etymologiae':
            book = int(re.search(r'isidore_(\d+)', page_file).group(1))
            before = len(out)
            isidore(page, abbrev, book, out)
            if len(out) - before < 5:
                del out[before:]
                isidore_stream(page, abbrev, book, out)
        else:
            raise SystemExit(f'no handler for {work}')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--only', help='convert a single work')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for work in MANIFEST:
        if args.only and work != args.only:
            continue
        rows = convert(work, args.src)
        dest = os.path.join(args.out, work + '.tess')
        with open(dest, 'w', encoding='utf-8') as fh:
            for ref, text in rows:
                fh.write(f'<{ref}>\t{text}\n')
        print(f'{work}: {len(rows)} lines -> {dest}')


if __name__ == '__main__':
    main()
