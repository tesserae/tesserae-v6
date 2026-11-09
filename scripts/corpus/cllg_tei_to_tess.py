#!/usr/bin/env python3
"""A Corpus Liberatum Linguae Graecae (CLLG, the Freed Corpus) TEI edition into .tess.

Generalizes perseus_greek_tei_to_tess.py to the shapes of the CLLG release of the TLG CD-ROM E texts
(CC0 text, CC BY 4.0 citation structure). The converter reads each file's own declaration of its
citation structure (teiHeader refsDecl, citeStructure/@match) and picks one of four line rules.

LINE RULES

1. Numbered leaves (the citeStructure ends in a numbered division or in verse lines: fragment, section,
   scholion, poem, chapter, letter, book, l ...). Every <div n="..."> inside the body is a division (type
   `edition` or `translation` never is). One .tess line is one deepest numbered division, cited by the path of
   the divisions' numbers joined with dots. A leaf that is verse (its <l> lines hold at least 80 percent of its
   Greek letters) gives one line per <l>, cited by the l's @n under the leaf's path (or counted from 1 when it has
   none). Text standing in a division before its sub-divisions is a line cited by the division's path with a final
   .0. A division labelled pr, praef, arg, pref, prol or proem counts as 0. A <div> without @n is transparent.

2. Page-cited prose (the citeStructure is `page`, `section/page`, `book/page`, `volume/page`, or the
   edition's column: <pb n="..."/> milestones, sometimes <milestone unit="volume"> and <milestone unit="column">).
   The text inside runs as the physical printed lines of the edition, separated by a newline in the XML or by
   <lb/>. One .tess line is one physical printed line, cited page.line with the line counted from 1 within the page
   (the counter restarts at every <pb>, and at a declared column milestone, whose n such as 704a then serves as the
   page; a citeStructure on <cb ed="PG" n="2792e"/> makes the column the page). The numbers of the enclosing numbered divisions come first (section.page.line, book.page.line), and the
   volume number comes first when the file has two or more volume milestones (volume.page.line). Lines that stand
   before the first numbered division of such a file are cited 0.page.line (the preface convention). Only <pb> elements
   whose @ed is the one the citeStructure names count. A heading's printed lines are counted but not written (a
   heading is dropped, as in the Perseus converter), so the numbers are those of the print. An empty line is
   dropped. A word hyphenated at the end of a printed line (also across a page break) is joined to its
   continuation and stays on the first line.

3. Verse or fragments counted by <lb n="..."/> (citeStructure ends in `lb`): the same machine as rule 2, with no
   page; the number is the lb's @n (the counter is restarted by each division).

4. Empty citeStructure (no declaration at all): one line per top-level <p>, <l> or list <item> in document order,
   numbered from 1. The converter prints `mode=paragraphs` so these files can be read by a person.

CLEANING (as the Perseus converter): notes, critical apparatus, headings and labels dropped; page and line breaks
become a sentinel; hyphenated words rejoined; runs of Latin tokens dropped; modifier-letter apostrophe and raised
stop normalized; NFC. Also: <seg rend="Marginalia"> content dropped; <supplied>, <unclear>, <add>, <del> and
<surplus> text kept without brackets; <gap> dropped; and the papyrological marks the print carried, namely runs of
three or more dots for a lacuna, square brackets, the paragraphos signs, underdots and daggers, are removed so that a
word broken by a bracket ("δυ]σπραξίας") is whole again.

    cllg_tei_to_tess.py SOURCE.xml OUT.tess --tag 'simpl. in phys.' [--parts-dir DIR] [--min-parts 2]

With --parts-dir it also writes <OUT stem>.part.<n>.tess for each top-level division when the edition has at least
--min-parts of them and the lines run deeper than one level. The last output line is
`RESULT mode=... lines=... tokens=... src_letters=... out_letters=... ratio=... dups=...`.
Exit 1 on a duplicate citation, 2 when more than 1.5 percent of the Greek letters of the body are not in any line.
"""
import argparse
import collections
import os
import re
import sys
import unicodedata

from lxml import etree

PREFACE = {'pr', 'praef', 'arg', 'pref', 'prol', 'proem'}
GREEK = re.compile(r'[Ͱ-Ͽἀ-῿]')
SENTINEL = '\x00'
XMLLANG = '{http://www.w3.org/XML/1998/namespace}lang'
DROP_ALL = {'note', 'app', 'gap', 'teiHeader', 'figure', 'milestone_other'}
DROP_COUNTED = {'head', 'label', 'trailer'}       # not written, but their printed lines are counted
BLOCK = {'p', 'l', 'lg', 'ab', 'item', 'list', 'quote', 'div', 'table', 'row', 'cb', 'titlePart', 'byline'}
HYPHENS = '-‐¬'


def local(el):
    return etree.QName(el).localname if isinstance(el.tag, str) else None


def is_part(el):
    return local(el) == 'div' and el.get('n') not in (None, '') and el.get('type') not in ('edition', 'translation')


def label(n):
    return '0' if n in PREFACE else n.strip()


class Ctx:
    def __init__(self, ed=None, col_ed=None, columns=False):
        self.ed = ed                # @ed the page citeStructure names, or None for any
        self.columns = columns      # column milestones are page-level units
        self.col_ed = col_ed
        self.cb = False             # <cb n="..."/> marks the page-level unit (Patrologia Graeca columns)
        self.cb_ed = None


def stream(el, ctx, drop=False, stop_parts=False, root=True):
    """Events in document order: ('t', text, dropped) ('nl',) ('pb', n) ('col', n) ('vol', n) ('lb', n)
    ('div+', label) ('div-',) ('tnl',). With stop_parts, numbered sub-divisions are skipped (their tails kept)."""
    if el.text:
        yield from _text(el.text, drop)
    for ch in el:
        name = local(ch)
        if name is None:
            pass
        elif name in DROP_ALL:
            pass
        elif name == 'bibl' and (ch.get(XMLLANG) or '') == 'eng':
            pass
        elif name == 'seg' and (ch.get('rend') or '') == 'Marginalia':
            pass
        elif name == 'pb':
            if ch.get('n') and (ctx.ed is None or ch.get('ed') == ctx.ed):
                yield ('pb', ch.get('n'))
            elif ch.get('n') is None:
                yield ('nl',)
        elif name == 'cb' and ctx.cb and ch.get('n') and (ctx.cb_ed is None or ch.get('ed') == ctx.cb_ed):
            yield ('pb', ch.get('n'))
        elif name == 'milestone':
            unit = ch.get('unit')
            if unit == 'volume' and ch.get('n'):
                yield ('vol', ch.get('n'))
            elif unit == 'column' and ctx.columns and ch.get('n') and (ctx.col_ed is None or ch.get('ed') == ctx.col_ed):
                yield ('col', ch.get('n'))
        elif name == 'lb':
            yield ('lb', ch.get('n'))
        elif name == 'space':
            yield ('t', ' ', drop)
        elif name == 'div':
            if is_part(ch):
                if not stop_parts:
                    yield ('div+', label(ch.get('n')))
                    yield from stream(ch, ctx, drop, stop_parts, False)
                    yield ('div-',)
            else:
                yield ('nl',)
                yield from stream(ch, ctx, drop, stop_parts, False)
                yield ('nl',)
        elif name in DROP_COUNTED:
            yield ('nl',)
            yield from stream(ch, ctx, True, stop_parts, False)
            yield ('nl',)
        elif name in BLOCK:
            yield ('nl',)
            yield from stream(ch, ctx, drop, stop_parts, False)
            yield ('nl',)
        else:
            yield from stream(ch, ctx, drop, stop_parts, False)
        if ch.tail:
            yield from _text(ch.tail, drop)


def _text(s, drop):
    parts = s.split('\n')
    for i, p in enumerate(parts):
        if i:
            yield ('tnl',)          # a newline in the XML text: a printed line break in page mode only
        if p:
            yield ('t', p, drop)


def pieces(el, ctx, stop_parts=False):
    """Text of el as a list of strings with SENTINEL at every line, page or column break (leaf mode)."""
    out = []
    for ev in stream(el, ctx, stop_parts=stop_parts):
        if ev[0] == 't':
            if not ev[2]:
                out.append(ev[1])
        elif ev[0] in ('nl', 'tnl', 'pb', 'col', 'lb', 'vol', 'div+', 'div-'):
            out.append(SENTINEL)
    return out


def drop_latin_runs(text):
    """Remove a run of tokens with no Greek letter in which at least two tokens hold Latin letters ("Vgl. Zonar.
    XIII 9, 10"): the German, Latin or French apparatus that the OCR left in the running text. A single Latin
    token is kept."""
    toks = text.split(' ')
    out, run = [], []

    def flush():
        if sum(1 for t in run if re.search('[A-Za-z]', t)) < 2:
            out.extend(run)
        run.clear()

    for t in toks:
        if GREEK.search(t):
            flush()
            out.append(t)
        else:
            run.append(t)
    flush()
    return ' '.join(out)


def drop_apparatus_brackets(text):
    """Editorial matter in the running text: a bracket that opens with a Latin letter or a digit ("[cf. Ps. CXVIII, 1]",
    "[Cod. φησίν]", "[fol. 57]", "[I.]") and a parenthesis of Latin words only ("(Mariandynorum regem)"). A bracket
    that opens with Greek is quoted text and stays (its square brackets are removed later)."""
    text = re.sub(r'\[\s*[A-Za-z0-9][^\]]*\]', ' ', text)
    return re.sub(r'\([^()Ͱ-Ͽἀ-῿]*[A-Za-z][^()Ͱ-Ͽἀ-῿]*\)', ' ', text)


def clean(pieces_):
    text = ''.join(pieces_)
    text = re.sub(r'(?<=[Ͱ-Ͽἀ-῿])\d*[' + HYPHENS + r']\s*' + SENTINEL + r'\s*', '', text)   # rejoin a hyphenated word
    text = text.replace(SENTINEL, ' ')
    text = unicodedata.normalize('NFC', re.sub(r'\s+', ' ', text)).strip()
    text = re.sub(r'(?<=[Ͱ-Ͽἀ-῿])\?(?=[Ͱ-Ͽἀ-῿])', '', text)
    text = drop_apparatus_brackets(text)
    text = re.sub(r'\*', ' ', text).replace('|', ' ')
    # Papyrological and editorial marks of the print: lacuna dots, brackets, paragraphos signs, daggers, underdots.
    text = re.sub(r'\.{3,}|…', ' ', text)
    text = re.sub(r'[\[\]⟦⟧⸏⸎†‡]', '', text)
    text = unicodedata.normalize('NFC', unicodedata.normalize('NFD', text).replace('̣', ''))
    text = drop_latin_runs(text)
    text = re.sub(r'^\d+[a-z]?\.?\s+(?=[^\d\s])', '', text.strip())
    text = text.replace('᾿', "'")
    text = re.sub('(?<=[β-δζθκ-ξπ-τφ-ψ])̓', "'", text)
    text = unicodedata.normalize('NFC', re.sub(r'\s+', ' ', text)).strip()
    return (text.replace('ʼ', "'").replace('’', "'").replace('᾽', "'").replace('·', ':'))


def letters(s):
    """Greek letters only: the numeral signs, the ano teleia and the like (categories Lm, Po, Sk) are not letters, and
    NFC rewrites them to characters outside the Greek blocks, so they would otherwise show as a loss."""
    return sum(1 for c in GREEK.findall(s) if unicodedata.category(c) in ('Lu', 'Ll', 'Lo', 'Lt'))


# ---------------------------------------------------------------- leaf mode

def child_parts(el):
    """Numbered divisions below el, looking through divisions that have no @n."""
    out = []
    for c in el:
        if local(c) == 'div':
            if is_part(c):
                out.append(c)
            else:
                out.extend(child_parts(c))
    return out


def walk(el, path, rows, ctx):
    parts = child_parts(el)
    verse = [d for d in el.iter() if local(d) == 'l']
    if not parts and verse:
        in_l = sum(letters(clean(pieces(ln, ctx))) for ln in verse)
        if in_l < 0.8 * letters(clean(pieces(el, ctx))):
            verse = []
    if not parts and verse:
        counter = 0
        for ln in verse:
            n = (ln.get('n') or '').strip()
            if not n:
                counter += 1
                n = str(counter)
            else:
                counter = int(n) if n.isdigit() else counter
            text = clean(pieces(ln, ctx))
            if text:
                rows.append((path + [n], text))
        return
    if not parts:
        text = clean(pieces(el, ctx))
        if text and path:
            rows.append((path, text))
        return
    lead = clean(pieces(el, ctx, stop_parts=True))
    if lead and path:
        rows.append((path + ['0'], lead))
    for c in parts:
        walk(c, path + [label(c.get('n'))], rows, ctx)


# ---------------------------------------------------------------- page / lb mode

def stream_rows(body, ctx, page_enabled):
    raw = []                      # dicts: path, vol, page, line, text
    st = {'path': [], 'page': None, 'vol': None, 'line': 0}
    cur = []

    def flush():
        nonblank = any(s.strip() for s, _ in cur)
        if nonblank:
            st['line'] += 1
            raw.append({'path': list(st['path']), 'vol': st['vol'], 'page': st['page'], 'line': st['line'],
                        'text': ''.join(s for s, d in cur if not d)})
        cur.clear()

    for ev in stream(body, ctx):
        k = ev[0]
        if k == 't':
            cur.append((ev[1], ev[2]))
        elif k == 'nl':
            flush()
        elif k == 'tnl':
            if page_enabled:
                flush()
            else:
                cur.append((' ', False))
        elif k in ('pb', 'col'):
            flush()
            if page_enabled:
                st['page'] = ev[1]
                st['line'] = 0
        elif k == 'vol':
            flush()
            st['vol'] = ev[1]
            if page_enabled:
                st['page'] = None
                st['line'] = 0
        elif k == 'lb':
            flush()
            n = ev[1]
            if n and n.strip().isdigit():
                st['line'] = int(n.strip()) - 1
        elif k == 'div+':
            flush()
            st['path'].append(ev[1])
            if not page_enabled:
                st['line'] = 0
        elif k == 'div-':
            flush()
            st['path'].pop()
    flush()
    # Join a word hyphenated at the end of a printed line to its continuation.
    for i, r in enumerate(raw):
        t = r['text'].rstrip()
        m = re.search(r'(?<=[Ͱ-Ͽἀ-῿])\d*[' + HYPHENS + r']$', t)
        if not m:
            continue
        for j in range(i + 1, min(i + 6, len(raw))):
            nxt = raw[j]['text'].lstrip()
            if nxt:
                first, _, rest = nxt.partition(' ')
                r['text'] = t[:m.start()] + first
                raw[j]['text'] = rest
                break
    return raw


# ---------------------------------------------------------------- mode

def declared(root):
    ms = [c.get('match') or '' for c in root.iter('{*}citeStructure')]
    return ms


def choose(root):
    ms = declared(root)
    ctx = Ctx()
    page = [m for m in ms if re.search(r'//(pb|cb)\b', m)]
    cols = [m for m in ms if "unit='column'" in m or 'unit="column"' in m]
    if page:
        e = re.search(r"@ed='([^']*)'", page[0])
        if re.search(r'//cb\b', page[0]):
            ctx.cb, ctx.cb_ed = True, (e.group(1) if e else None)
            ctx.ed = '\x00no pb'            # a file that pages by column ignores its pb elements
        else:
            ctx.ed = e.group(1) if e else None
        if cols:
            ctx.columns = True
            e = re.search(r"@ed='([^']*)'", cols[0])
            ctx.col_ed = e.group(1) if e else None
        return 'pages', ctx
    if any(re.search(r'(^|/)lb$', m) for m in ms):
        return 'lb', ctx
    if not ms:
        return 'paragraphs', ctx
    return 'leaves', ctx


def paragraph_rows(body, ctx):
    rows = []
    n = 0
    for el in body.iter():
        if local(el) not in ('p', 'l', 'item'):
            continue
        if any(local(a) in ('p', 'l', 'item', 'head', 'note', 'label') for a in el.iterancestors() if a is not body):
            continue
        text = clean(pieces(el, ctx))
        if text and GREEK.search(text):
            n += 1
            rows.append(([str(n)], text))
    return rows


def raw_text(el, out):
    """Body text collected without the structure rules (so a loss in them shows): every text node except notes,
    apparatus, gaps, headings, labels, marginalia and English bibliography."""
    out.append(el.text or '')
    for ch in el:
        name = local(ch)
        skip = (name in DROP_ALL or name in DROP_COUNTED or (name == 'seg' and (ch.get('rend') or '') == 'Marginalia')
                or (name == 'bibl' and (ch.get(XMLLANG) or '') == 'eng'))
        if name is not None and not skip:
            raw_text(ch, out)
        out.append(ch.tail or '')
    return out


def raw_letters(el):
    """Greek letters of the body text after the bracket and parenthesis apparatus is taken out, as the lines drop it."""
    return letters(drop_apparatus_brackets(unicodedata.normalize('NFC', ' '.join(raw_text(el, [])))))


def convert(src, tag):
    tree = etree.parse(src, etree.XMLParser(recover=True, huge_tree=True))
    root = tree.getroot()
    body = root.find('.//{*}body')
    mode, ctx = choose(root)
    if mode == 'leaves':
        rows = []
        walk(body, [], rows, ctx)
    elif mode == 'paragraphs':
        rows = paragraph_rows(body, ctx)
    else:
        page_enabled = mode == 'pages'
        raw = stream_rows(body, ctx, page_enabled)
        vols = {r['vol'] for r in raw if r['vol']}
        depth = max([len(r['path']) for r in raw] or [0])
        rows = []
        for r in raw:
            text = clean([r['text']])
            if not text:
                continue
            p = []
            if len(vols) >= 2 and r['vol']:
                p.append(r['vol'])
            p += r['path'] if r['path'] or not depth else ['0'] * depth     # a line before the first division is its preface
            if page_enabled:
                p.append(r['page'] if r['page'] is not None else '0')
            p.append(str(r['line']))
            rows.append((p, text))
    rows = [(p, t) for p, t in rows if GREEK.search(t)]
    src_letters = raw_letters(body)
    lines = [(f'{tag} ' + '.'.join(p), t) for p, t in rows]
    return mode, rows, lines, src_letters


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source')
    ap.add_argument('out')
    ap.add_argument('--tag', required=True)
    ap.add_argument('--parts-dir')
    ap.add_argument('--min-parts', type=int, default=2)
    args = ap.parse_args()

    mode, rows, lines, src_letters = convert(args.source, args.tag)
    if not rows:
        sys.exit('no citable lines found')
    refs = [r for r, _ in lines]
    dups = [r for r, c in collections.Counter(refs).items() if c > 1]
    out_letters = sum(letters(t) for _, t in lines)
    ratio = out_letters / src_letters if src_letters else 1.0
    tokens = sum(1 for _, t in lines for w in t.split() if GREEK.search(w))
    print(f'{len(lines)} lines; Greek letters in source body {src_letters}, in lines {out_letters} ({ratio:.4f}); '
          f'duplicate citations {len(dups)}')
    for d in dups[:10]:
        print('  DUPLICATE', d)

    with open(args.out, 'w', encoding='utf-8', newline='') as fh:
        for ref, text in lines:
            fh.write(f'<{ref}>\t{text}\n')

    nparts = 0
    if args.parts_dir:
        by_top = collections.OrderedDict()
        for (p, _), (ref, text) in zip(rows, lines):
            by_top.setdefault(p[0], []).append((ref, text))
        if len(by_top) >= args.min_parts and any(len(p) > 1 for p, _ in rows):
            stem = os.path.basename(args.out)[:-5]
            bad = [b for b in by_top if not re.fullmatch(r'[A-Za-z0-9_-]+', b)]
            if bad:
                print('PARTS NOT WRITTEN: top-level labels not usable in a file name:', bad[:5], file=sys.stderr)
            else:
                for b, rs in by_top.items():
                    path = os.path.join(args.parts_dir, f'{stem}.part.{b}.tess')
                    with open(path, 'w', encoding='utf-8', newline='') as fh:
                        for ref, text in rs:
                            fh.write(f'<{ref}>\t{text}\n')
                    nparts += 1
    print(f'RESULT mode={mode} lines={len(lines)} tokens={tokens} src_letters={src_letters} out_letters={out_letters} '
          f'ratio={ratio:.4f} dups={len(dups)} parts={nparts}')
    if dups:
        sys.exit(1)
    if ratio < 0.985:
        print('WARNING: more than 1.5% of the Greek is not in any line', file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
