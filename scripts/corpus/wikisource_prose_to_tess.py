#!/usr/bin/env python3
"""Convert Latin Wikisource wikitext of chaptered prose into .tess files.

Handles the works whose books are subpages ("Work/Liber I") with chapter
headings inside each page:

  gregory   Gregory of Tours, Historiarum libri X   (== N. title == headings)
  geoffrey  Geoffrey of Monmouth, Historia regum Britanniae (===N=== headings,
            an all-capitals bold summary line under each)

Line references are book.chapter.paragraph (chapter pr and paragraph counted
from 1 within the chapter), e.g. <greg. tur. hist. 2.9.1>. Text before the
first chapter heading of a book (a prologue) is chapter `pr`. The chapter
titles of Gregory's headings and the bold summary lines of Geoffrey are
capitula added by the editor of the page and are kept out of the text.

Usage: wikisource_prose_to_tess.py {gregory|geoffrey} SRC_DIR OUT_DIR
"""
import html
import re
import sys
from pathlib import Path

ROMAN = {'I': 1, 'V': 5, 'X': 10}


def roman(s):
    n = 0
    s = s.upper()
    for i, c in enumerate(s):
        v = ROMAN[c]
        if i + 1 < len(s) and ROMAN[s[i + 1]] > v:
            n -= v
        else:
            n += v
    return n


def strip_templates(s):
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r'\{\{[^{}]*\}\}', '', s)
    s = re.sub(r'\{\|.*?\|\}', '', s, flags=re.S)
    return s


def clean(s):
    s = strip_templates(s)
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
    s = re.sub(r'\[\[(?:Imago|Image|File|en|it|fr|de):[^\]]*\]\]', '', s)
    s = re.sub(r'\[\[[^\]|]*\|([^\]]*)\]\]', r'\1', s)
    s = re.sub(r'\[\[([^\]]*)\]\]', r'\1', s)
    s = re.sub(r"'{2,}", '', s)
    s = re.sub(r'</?(div|span|br|small|center|big|poem|blockquote)[^>]*>', '\n', s)
    s = re.sub(r'__[A-Z]+__', '', s)
    s = html.unescape(s)
    return s


def paragraphs(block):
    out = []
    for p in re.split(r'\n\s*\n', block):
        p = re.sub(r'\s+', ' ', p).strip()
        if p:
            out.append(p)
    return out


def book_chapters(text, kind):
    """[(chapter label, [paragraphs])] for one book page."""
    text = re.sub(r'\{\{titulus2.*?\n\}\}', '', text, flags=re.S)
    if kind == 'gregory':
        head = re.compile(r'^==\s*(\d+)\.?[^=\n]*==\s*$', re.M)
    else:
        head = re.compile(r'^===\s*(\d+)\s*===\s*$', re.M)
    pieces = head.split(text)
    chapters = []
    pre = paragraphs(clean(pieces[0]))
    if pre:
        chapters.append(('pr', pre))
    for i in range(1, len(pieces), 2):
        body = clean(pieces[i + 1])
        ps = paragraphs(body)
        if kind == 'geoffrey' and ps and re.fullmatch(r"[^a-z]*[A-Z][^a-z]*", ps[0]) and len(ps[0]) < 400:
            ps = ps[1:]  # bold all-capitals summary of the chapter
        chapters.append((pieces[i], ps))
    return chapters


CFG = {
    'gregory': ('gregory_of_tours.historiarum_libri_x', 'greg. tur. hist.', 'Historiarum_Francorum_libri_X__Liber_{}.wiki', 10),
    'geoffrey': ('geoffrey_of_monmouth.historia_regum_britanniae', 'gal. mon. hrb.', 'Historia_Regum_Britanniae__Liber_{}.wiki', 12),
}
ROMANS = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']


def main():
    kind, src, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    name, tag, pat, nb = CFG[kind]
    lines = []
    parts = {}
    for b in range(1, nb + 1):
        f = src / pat.format(ROMANS[b - 1])
        chs = book_chapters(f.read_text(encoding='utf-8'), kind)
        seen = set()
        rows = []
        for lab, ps in chs:
            assert lab not in seen, f'{kind} book {b}: duplicate chapter {lab}'
            seen.add(lab)
            for k, p in enumerate(ps, 1):
                rows.append(f'<{tag} {b}.{lab}.{k}>\t{p}')
        parts[b] = rows
        lines += rows
    if kind == 'gregory':
        pre = book_chapters((src / 'Historiarum_Francorum_libri_X__Praefatio.wiki').read_text(encoding='utf-8'), kind)
        ps = [p for _l, pl in pre for p in pl]
        pr_rows = [f'<{tag} pr.1.{k}>\t{p}' for k, p in enumerate(ps, 1)]
        lines = pr_rows + lines
        parts[1] = pr_rows + parts[1]
    out.mkdir(parents=True, exist_ok=True)
    (out / f'{name}.tess').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for b, rows in parts.items():
        (out / f'{name}.part.{b}.tess').write_text('\n'.join(rows) + '\n', encoding='utf-8')
    print(f'{name}: {len(lines)} lines, {len(parts)} parts')


if __name__ == '__main__':
    main()
