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

Later addition (2026-10-08): the two minor works transmitted with the
Aurelius Victor corpus but not by him, De Viris Illustribus and the Origo
Gentis Romanae ('victor/victor.ill.html', 'victor/victor.origio.html').
Both are pseudonymous (authorship unknown; traditionally bound with
Aurelius Victor's own De Caesaribus and Epitome de Caesaribus, already in
the corpus under 'aurelius_victor.*'), so their files are named
'pseudo_aurelius_victor.*' after this repository's existing convention for
anonymous works attached to a named author's corpus (see
'pseudo_victor_vitensis.*'). See `de_viris_illustribus` and
`origo_gentis_romanae` below for the two pages' differing markup and the
numbering gaps each has in the source transcription.

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
  vegetius.epitoma_rei_militaris veg. mil.     book.chapter (arabic; source
                                               numerals are roman). All
                                               front matter before chapter I
                                               goes to '.pr.N' in document
                                               order: for books 2-4 that is
                                               just the capitula list (all
                                               its own chapter headings in
                                               one paragraph, not chapter
                                               text) then the book preface,
                                               so '.pr.1' = capitula,
                                               '.pr.2' = preface; book 1
                                               carries an extra work-wide
                                               preface and a one-line
                                               epigraph ahead of its own
                                               capitula and preface, so
                                               '.pr.1'/'.pr.2' = those two,
                                               '.pr.3' = capitula, '.pr.4' =
                                               the book 1 preface proper. A
                                               paragraph with no numeral
                                               that follows chapters already
                                               under way (book 3's closing
                                               dedication after its titled
                                               'REGULAE BELLORUM GENERALES'
                                               chapter; book 4's transition
                                               from land to naval warfare
                                               between chapters 30 and 31)
                                               is appended to the preceding
                                               chapter's line rather than
                                               given its own reference, to
                                               keep references monotonic.

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
    'vegetius.epitoma_rei_militaris': [f'vegetius{b}.html' for b in range(1, 5)],
    'grattius.cynegetica': ['grattius.html'],
    'germanicus.aratea': ['germanicus.html'],
    'solinus.collectanea_rerum_memorabilium': ['solinus5.html'],
    'censorinus.de_die_natali': ['censorinus.html'],
    'obsequens.liber_de_prodigiis': ['obsequens.html'],
    'pseudo_aurelius_victor.de_viris_illustribus': ['victor.ill.html'],
    'pseudo_aurelius_victor.origo_gentis_romanae': ['victor.origio.html'],
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
    'vegetius.epitoma_rei_militaris': 'veg. mil.',
    'grattius.cynegetica': 'grat. cyn.',
    'germanicus.aratea': 'germ. arat.',
    'solinus.collectanea_rerum_memorabilium': 'solin.',
    'censorinus.de_die_natali': 'censorin.',
    'obsequens.liber_de_prodigiis': 'obseq.',
    'pseudo_aurelius_victor.de_viris_illustribus': 'ps-vict. vir. ill.',
    'pseudo_aurelius_victor.origo_gentis_romanae': 'ps-vict. orig.',
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


def vegetius(page, abbrev, book, out):
    """Vegetius Epitoma Rei Militaris: plain (non-bold) 'ROMAN. text' chapter
    markers. The first roman-numeral-led paragraph in each book is a
    capitula list (it runs through every chapter heading in one block, e.g.
    'I. ... II. ... III. ...') rather than chapter I itself. It and any
    preface paragraphs before real chapter I are numbered '.pr.N' in
    document order (see module docstring for what each N is per book), kept
    under one string tag so references stay monotonic. A closing chapter
    can be parenthesised, bare '(XXVIII.)' (book 1) or with its own rubric
    '(XXVI. REGULAE BELLORUM GENERALES)' (book 3). A paragraph with no
    numeral that follows chapters already under way (book 3's closing
    dedication, book 4's land-to-naval transition) is appended to the
    preceding chapter's text rather than given its own reference."""
    pre = 0
    seen_capitula = False
    chap = None
    last_num = 0
    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        txt = clean(inner)
        if not txt:
            continue
        m = re.match(r'^\(([IVXLCDM]+)\.\s*([^)]*)\)\s*(.*)', txt, re.S)
        if m and roman_to_int(m.group(1)) is not None:
            num_str, rubric, rest = m.group(1), m.group(2).strip(), m.group(3).strip()
            body = ' '.join(t for t in (rubric, rest) if t)
        else:
            m = re.match(r'^([IVXLCDM]+)\.\s+(.*)', txt, re.S)
            num_str, body = (m.group(1), m.group(2)) if m and roman_to_int(m.group(1)) is not None else (None, None)
        if num_str is not None:
            if not seen_capitula:
                seen_capitula = True
                pre += 1
                flush(out, abbrev, f'{book}.pr.{pre}', [txt])
                continue
            num = roman_to_int(num_str)
            if num <= last_num:
                num = last_num + 1  # source misprint: keep numbering forward
            last_num = num
            chap = num
            flush(out, abbrev, f'{book}.{chap}', [body])
            continue
        if chap is None:
            pre += 1
            flush(out, abbrev, f'{book}.pr.{pre}', [txt])
        elif out:
            out[-1] = (out[-1][0], f'{out[-1][1]} {txt}')


def single_poem_verse(page, abbrev, out):
    """Grattius Cynegetica and Germanicus Aratea: single-book continuous
    verse, one line per '<br>'. Line-number spans every 5 lines
    ('<span style="font-size: 80%;">N</span>', with leading &nbsp; padding)
    are editorial and dropped rather than kept as text."""
    n = 0
    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        body = re.sub(r'(?:&nbsp;)*<span[^>]*>\s*\d+\s*</span>', '', inner)
        txt = clean(body, keep_breaks=True)
        for verse in txt.split('\n'):
            verse = verse.strip()
            if not verse:
                continue
            n += 1
            flush(out, abbrev, str(n), [verse])


def solinus(page, abbrev, out):
    """Solinus Collectanea (Mommsen 2nd ed., thelatinlibrary's single-page
    'solinus5.html'): a dedication heading (dropped) opens a preface of
    plain arabic-numbered sections ('pr'); '<b>ROMAN.</b>' opens each
    chapter, immediately followed by its own arabic section numbering:
    '<b>I.</b>1 Sunt qui...'. Sections and the paragraphs between them are
    concatenated into one stream per chapter, since a section can span
    several source paragraphs, then re-split at each inline 'N ' marker."""
    chapters = []
    cur, parts = 'pr', []
    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        txt = clean(inner)
        if not txt or re.fullmatch(r'(?i)SOLINVS ADVENTO SALVTEM', txt):
            continue
        # the source is inconsistent about whether the period after the
        # roman numeral sits inside or outside '<b>...</b>' ('VI.</b>1' vs
        # 'VII</b>.1'); clean() turns the closing tag into a space either
        # way, so tolerate a space before the period too.
        m = re.match(r'^([IVXLCDM]+)\s*\.\s*(.*)', txt, re.S)
        if m and roman_to_int(m.group(1)) is not None:
            if parts:
                chapters.append((cur, ' '.join(parts)))
            cur, parts = roman_to_int(m.group(1)), [m.group(2)]
        else:
            parts.append(txt)
    if parts:
        chapters.append((cur, ' '.join(parts)))

    sect_rx = re.compile(r'(?:^|(?<=\s))(\d+)\s+(?=[A-Z\[*])')
    for chap, text in chapters:
        marks = list(sect_rx.finditer(text))
        if not marks:
            flush(out, abbrev, f'{chap}.1', [text])
            continue
        for i, mk in enumerate(marks):
            start = mk.end()
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            body = text[start:end].strip()
            if body:
                flush(out, abbrev, f'{chap}.{mk.group(1)}', [body])


def censorinus(page, abbrev, out):
    """Censorinus De Die Natali: single (undivided) book; bold roman-numeral
    chapter markers, one paragraph per chapter (same shape as
    chapter_bold_prose, but with no book level since the work has none)."""
    chap, par = 'pr', 0
    last_num = 0
    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        m = re.match(r'(?is)\s*(?:<a[^>]*>\s*</a>\s*)?<b>\s*([IVXLCDM]+)\s*\.?\s*(.*?)</b>\s*(.*)',
                     inner)
        if m and roman_to_int(m.group(1)) is not None:
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
                flush(out, abbrev, f'{chap}.{par}', [text])
            continue
        par += 1
        flush(out, abbrev, f'{chap}.{par}', [clean(inner)])


def obsequens(page, abbrev, out):
    """Julius Obsequens: every entry's anchor is placed as a TRAILING marker
    at the end of the PRECEDING entry's html ('...habita.<a name="2"></a>'),
    pointing forward, rather than opening its own text (only the very first
    entry opens with its own anchor); an entry's actual text then starts the
    next source paragraph with no anchor of its own. So anchors and text are
    tokenized as one continuous stream across paragraph breaks, not per
    paragraph. Consular-year headings ('<b>...coss. [...]</b>', no anchor)
    are the editor's and are dropped from the text. The
    anchor name is used as the reference verbatim, including the source's
    own letter-suffixed entries for a numbering gap ('27a', '27b', each
    with their own '27a.2' etc.): that is the traditional citation for this
    work, kept even though the generic validator's numeric-only
    monotonicity check will (correctly, harmlessly) flag the handful of
    transitions into a lettered entry as non-monotonic."""
    used = set()
    pending_ref = None
    pending_year = ''
    parts = []

    def emit_pending():
        nonlocal pending_ref, parts, pending_year
        if pending_ref is not None:
            body = ' '.join(p for p in parts if p).strip()
            body = re.sub(rf'^{re.escape(pending_ref)}\.?\s*', '', body)
            # The page's consular-year headings are the editor's, not the
            # author's, so they are not written into the searchable text.
            pending_year = ''
            if body:
                ref = pending_ref
                if ref in used:
                    # source misprint: an anchor name reused (e.g. two
                    # '<a name="15.4">' in a row); disambiguate forward
                    base, n = ref, 1
                    while f'{base}.{n}' in used:
                        n += 1
                    ref = f'{base}.{n}'
                used.add(ref)
                flush(out, abbrev, ref, [body])
        parts = []

    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        if '<b>' in inner.lower() and '<a name' not in inner.lower():
            txt = clean(inner)
            if txt:
                pending_year = txt
            continue
        pieces = re.split(r'(?is)<a\s+name="([^"]+)"\s*>\s*</a>', inner)
        parts.append(clean(pieces[0]))
        for i in range(1, len(pieces), 2):
            emit_pending()
            pending_ref = pieces[i]
            parts = [clean(pieces[i + 1]) if i + 1 < len(pieces) else '']
    emit_pending()


def de_viris_illustribus(page, abbrev, out):
    """Pseudo-Aurelius Victor, De Viris Illustribus (thelatinlibrary's
    single-page 'victor.ill.html'): each biographical notice is one <P>
    block opening with a bold arabic chapter marker ('<B>N</B>'), its own
    prose then divided by inline '<FONT size=2>n</FONT>' arabic section
    markers. An embedded verse quotation (ch. 4, 35) breaks the source HTML
    into extra <P> blocks carrying no marker of their own, and one
    continuation (ch. 77 into 78, a parenthetical aside on Pompey's death)
    likewise opens a new <P> with no leading marker; both are folded into
    the chapter in progress by concatenating every block's raw markup until
    the next chapter marker, before splitting on the FONT tags. Two section
    numbers in ch. 18 (3 and 4, a quoted fable) are plain digits with no
    FONT wrapper of their own; these are matched too (a digit immediately
    between a closing and opening '<I>' quotation tag). Three section
    numbers are simply absent from the source transcription with no
    markup residue at all (ch. 8 has no '3', ch. 42 no '4', ch. 49 no
    '13'): the numbering here keeps the source's own gaps rather than
    renumbering forward, since nothing is missing from the TEXT, only from
    the editor's count of it."""
    chapters = []
    cur, parts = 'pr', []
    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        m = re.match(r'(?is)^\s*<B>\s*(\d+)\s*</B>\s*(.*)', inner)
        if m:
            if parts:
                chapters.append((cur, ' '.join(parts)))
            cur, parts = int(m.group(1)), [m.group(2)]
        else:
            parts.append(inner)
    if parts:
        chapters.append((cur, ' '.join(parts)))

    sect_rx = re.compile(
        r'(?is)<FONT\s+size=2>\s*(\d+)\s*</FONT>|(?<=</I>)\s*(\d+)\s*(?=<I>)')
    for chap, html_text in chapters:
        marks = list(sect_rx.finditer(html_text))
        if not marks:
            txt = clean(html_text)
            if txt:
                flush(out, abbrev, f'{chap}.1', [txt])
            continue
        for i, mk in enumerate(marks):
            start = mk.end()
            end = marks[i + 1].start() if i + 1 < len(marks) else len(html_text)
            body = clean(html_text[start:end])
            if body:
                num = mk.group(1) or mk.group(2)
                flush(out, abbrev, f'{chap}.{num}', [body])


def origo_gentis_romanae(page, abbrev, out):
    """Pseudo-Aurelius Victor, Origo Gentis Romanae (thelatinlibrary's
    single-page 'victor.origio.html', mislabeled 'EPITOME DE CAESARIBUS' in
    its own <title> tag, a stray leftover from the companion page). An
    unnumbered dedicatory preface opens the work ('pr'), then '<b>N</b>'
    marks each of the 23 chapters, immediately followed by its own
    arabic-numbered sections run inline as plain text ('1 Primus...', '2
    Isque...'), not wrapped in a tag as on the companion De Viris
    Illustribus page. A section number sometimes opens a clause that
    continues in lower case rather than a new sentence (e.g. ch. 13.3 'cum
    cognovisset...'), so the split only requires the digit to be followed
    by a letter, not a capital. Quoted verse (Vergil, Ennius, the Carmen
    Saliare) and one marked lacuna (a row of dots, ch. 3, where the unique
    manuscript itself is defective) break the source HTML into extra <P>
    blocks with no marker of their own; these are folded into the section
    in progress by concatenating every block's cleaned text until the next
    digit marker (the lacuna dots themselves are dropped as noise, so nothing
    marks the gap in the running text, a loss of information this converter
    does not have a convention for and leaves marked only in this
    docstring). Chapter 4 is missing its own '4' in the source transcription
    (3 runs straight into 5); the gap is kept rather than renumbered, for
    the same reason as the De Viris Illustribus gaps above."""
    chapters = []
    cur, parts = 'pr', []
    for attrs, inner in paragraphs(page):
        if is_noise(attrs, inner):
            continue
        m = re.match(r'(?is)^\s*<b>\s*(\d+)\s*</b>\s*,?\s*(.*)', inner)
        if m:
            if parts:
                chapters.append((cur, clean(' '.join(parts))))
            cur, parts = int(m.group(1)), [m.group(2)]
        else:
            parts.append(inner)
    if parts:
        chapters.append((cur, clean(' '.join(parts))))

    sect_rx = re.compile(r'(?:^|(?<=[\s)]))(\d+)\s+(?=[A-Za-z\[(])')
    for chap, text in chapters:
        marks = list(sect_rx.finditer(text))
        if not marks:
            if text:
                flush(out, abbrev, f'{chap}.1', [text])
            continue
        for i, mk in enumerate(marks):
            start = mk.end()
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            body = text[start:end].strip()
            if body:
                flush(out, abbrev, f'{chap}.{mk.group(1)}', [body])


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
        elif work == 'vegetius.epitoma_rei_militaris':
            book = int(re.search(r'vegetius(\d)', page_file).group(1))
            vegetius(page, abbrev, book, out)
        elif work in ('grattius.cynegetica', 'germanicus.aratea'):
            single_poem_verse(page, abbrev, out)
        elif work == 'solinus.collectanea_rerum_memorabilium':
            solinus(page, abbrev, out)
        elif work == 'censorinus.de_die_natali':
            censorinus(page, abbrev, out)
        elif work == 'obsequens.liber_de_prodigiis':
            obsequens(page, abbrev, out)
        elif work == 'pseudo_aurelius_victor.de_viris_illustribus':
            de_viris_illustribus(page, abbrev, out)
        elif work == 'pseudo_aurelius_victor.origo_gentis_romanae':
            origo_gentis_romanae(page, abbrev, out)
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
