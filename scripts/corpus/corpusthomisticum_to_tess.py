#!/usr/bin/env python3
"""Convert Corpus Thomisticum pages of the Summa Theologiae into .tess files.

Same reference scheme as the held Prima Pars (scripts/corpus/batch3_to_tess.py,
`aquin. sth1a. Q.A.P`): Q the question, A the article (0 for the question's
prologue), P the paragraph counted in article order (arguments, sed contra,
corpus, replies), following the site's own paragraph labels.

Parts (Corpus Thomisticum page series and the label on its paragraphs):
  sth2*.html  I-II   -> aquinas.summa_theologiae_2  tag `aquin. sth1a2ae.`  q. 1-114
  sth3*.html  II-II  -> aquinas.summa_theologiae_3  tag `aquin. sth2a2ae.`  q. 1-189
  sth4*.html  III    -> aquinas.summa_theologiae_4  tag `aquin. sth3a.`     q. 1-90

Usage: corpusthomisticum_to_tess.py SRC_DIR OUT_DIR
"""
import glob
import html as html_mod
import os
import re
import sys

PARTS = {
    'sth2': ('I-II', 'aquinas.summa_theologiae_2', 'aquin. sth1a2ae.', 114),
    'sth3': ('II-II', 'aquinas.summa_theologiae_3', 'aquin. sth2a2ae.', 189),
    'sth4': ('III', 'aquinas.summa_theologiae_4', 'aquin. sth3a.', 90),
}


def strip_tags(s):
    s = re.sub(r'<script.*?</script>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html_mod.unescape(s)
    s = re.sub('[⁠​‎­﻿]', '', s)
    s = re.sub(r'\s+([,.;:?!)])', r'\1', s)
    s = re.sub(r'\(\s+', '(', s)
    return re.sub(r'\s+', ' ', s).strip()


def labeled_rows(src, prefix):
    """[(q, a, label, text)] in document order; label is the site's own paragraph
    label (pr., arg. N, s. c., co., ad N). a is 0 for a question prologue."""
    label, name, tag, last = PARTS[prefix]
    rows = []
    for path in sorted(glob.glob(os.path.join(src, prefix + '*.html'))):
        t = open(path, 'rb').read().decode('iso-8859-1')
        for m in re.finditer(r'<P TITLE="([^"]+)">(.*?)</P>', t, flags=re.S):
            mm = re.match(re.escape(label) + r' q\. (\d+)(?: a\. (\d+))?\s*(.*)$', m.group(1).strip())
            if not mm:
                continue
            q = int(mm.group(1))
            a = int(mm.group(2)) if mm.group(2) else 0
            body = re.sub(r'<SPAN CLASS="ref">.*?</SPAN>', '', m.group(2), flags=re.S)
            text = strip_tags(body)
            if text:
                rows.append((q, a, mm.group(3).strip() or 'pr.', text))
    return rows


def convert(src, prefix):
    label, name, tag, last = PARTS[prefix]
    rows = [(q, a, t) for q, a, _l, t in labeled_rows(src, prefix)]
    qs = {q for q, _a, _t in rows}
    missing = sorted(set(range(1, last + 1)) - qs)
    assert not missing, f'{name}: missing questions {missing}'
    counter = {}
    units = []
    for q, a, text in rows:
        p = counter.get((q, a), 0) + 1
        counter[(q, a)] = p
        units.append((f'{tag} {q}.{a}.{p}', text))
    return name, units


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for prefix in PARTS:
        name, units = convert(src, prefix)
        with open(os.path.join(out, name + '.tess'), 'w', encoding='utf-8') as fh:
            for ref, text in units:
                fh.write(f'<{ref}>\t{text}\n')
        print(f'{name}: {len(units)} lines')


if __name__ == '__main__':
    main()
