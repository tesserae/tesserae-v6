#!/usr/bin/env python3
"""Convert the Latin Wikisource transcription of the Gesta Romanorum
(Oesterley, Berlin 1872) into one .tess file.

The article "Gesta Romanorum (Oesterley)/N" transcludes the proofread pages
of the print edition, so the text is taken from the rendered HTML
(wikisource_fetch.py --html), not from the wikitext. One page is one
chapter (a tale and, as a rule, its moralisation). Reference: <gest. rom. N.P>
with N the edition's chapter number and P the paragraph within it (the tale,
then the Moralisatio).

Removed: the footnote apparatus (variant readings), the edition's page-boundary and manuscript-sigla markers in square
brackets with digits (such as [2b]), running heads, the chapter's own title
line. Kept: every word of the Latin.

Usage: wikisource_gesta_to_tess.py SRC_HTML_DIR OUT_DIR
"""
import html
import re
import sys
from pathlib import Path

NAME = 'gesta_romanorum.gesta_romanorum_oesterley'
TAG = 'gest. rom.'


def page_paragraphs(raw):
    i = raw.find('prp-pages-output')
    if i < 0:
        return []
    s = raw[i + len('prp-pages-output" lang="la">'):]
    s = re.sub(r'<div class="centertext".*?</div>',
               lambda m: '' if 'Cap.' in m.group(0) else m.group(0), s, flags=re.S)
    s = re.sub(r'<span class="pagenum".*?</span></span></span>', '', s, flags=re.S)
    s = re.sub(r'<sup[^>]*class="reference".*?</sup>', '', s, flags=re.S)
    s = re.sub(r'<div class="ws-noexport".*?</div>', '', s, flags=re.S)
    s = re.sub(r'</p>|<br\s*/?>\s*<br\s*/?>', '\n\n', s)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(s)
    s = re.sub(r'\[\s*\d+\s*[a-z]?\s*\]', ' ', s)
    out = []
    for blk in re.split(r'\n\s*\n', s):
        t = re.sub(r'\s+', ' ', blk).strip()
        t = re.sub(r'\s+([,.;:?!)\]])', r'\1', t)
        t = re.sub(r'([(\[])\s+', r'\1', t)
        if t and not t.startswith('↑'):  # footnote apparatus (variant readings)
            out.append(t)
    return out


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    pages = {}
    for f in src.glob('*.html'):
        m = re.search(r'__(\d+)\.html$', f.name)
        if m:
            pages[int(m.group(1))] = f
    lines = []
    for n in sorted(pages):
        ps = page_paragraphs(pages[n].read_text(encoding='utf-8'))
        for k, p in enumerate(ps, 1):
            lines.append(f'<{TAG} {n}.{k}>\t{p}')
    out.mkdir(parents=True, exist_ok=True)
    (out / f'{NAME}.tess').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{NAME}: {len(lines)} lines, {len(pages)} chapters, first {min(pages)} last {max(pages)}')


if __name__ == '__main__':
    main()
