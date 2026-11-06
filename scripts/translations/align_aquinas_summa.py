#!/usr/bin/env python3
"""Paragraph-exact English for Summa Theologiae I-II, II-II and III.

The Fathers of the English Dominican Province (second and revised edition,
1920 to 1922, first edition 1911 to 1925), Project Gutenberg #17897 (I-II),
#18755 (II-II) and #19950 (III). Same method as the Prima Pars in
align_batch3.py: the English marks articles with "[I-II, Q. 1, Art. 1]" and
paragraphs with "Objection N:", "On the contrary,", "I answer that,",
"Reply Obj. N:", which key one to one onto Corpus Thomisticum's paragraph labels
(arg. N, s. c., co., ad N) in the order the .tess paragraphs were built
(corpusthomisticum_to_tess.labeled_rows). A second sed contra ("s. c. 2") has
no English marker of its own and stays unmatched.

Usage: align_aquinas_summa.py --part {2|3|4} --ct SRC_DIR --english PG.txt \
          --tess FILE.tess --out OUT.json
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'corpus'))
from align_batch3 import emit, tess_refs  # noqa: E402
import corpusthomisticum_to_tess as CT  # noqa: E402

PARTS = {
    '2': ('sth2', 'aquinas.summa_theologiae_2', 'I-II', 'aquin. sth1a2ae.', '17897', 'Second Part, First Part (Prima Secundae)'),
    '3': ('sth3', 'aquinas.summa_theologiae_3', 'II-II', 'aquin. sth2a2ae.', '18755', 'Second Part, Second Part (Secunda Secundae)'),
    '4': ('sth4', 'aquinas.summa_theologiae_4', 'III', 'aquin. sth3a.', '19950', 'Third Part (Tertia Pars)'),
}


def parse_english(path, label):
    t = open(path, encoding='utf-8', errors='replace').read()
    t = t.split('*** START OF')[-1].split('*** END OF')[0]
    art = re.compile(r'\[' + re.escape(label) + r'[.,]?\s*Q\.\s*(\d+),\s*Art\.\s*(\d+)\]')
    arts = [(m.start(), int(m.group(1)), int(m.group(2))) for m in art.finditer(t)]
    out = {}

    def clean(x):
        x = x.replace('_', ' ')
        return re.sub(r'\s+', ' ', x).strip()

    for m in re.finditer(r'^QUESTION (\d+)\s*$', t, flags=re.M):
        q = int(m.group(1))
        nxt = next((s for s, qq, aa in arts if s > m.end()), len(t))
        seg = t[m.end():nxt]
        seg = re.sub(r'\n[A-Z]+ ARTICLE\s*$', '', seg.rstrip())
        seg = re.sub(r'^\s*[A-Z, \'\?()0-9\n]+\n', '', seg)
        seg = re.sub(r'\(In \w+ Articles?\)', '', seg)
        body = clean(seg)
        if len(body.split()) >= 10:
            out[(q, 0, 'pr.')] = body
    for i, (s, q, a) in enumerate(arts):
        end = arts[i + 1][0] if i + 1 < len(arts) else len(t)
        seg = t[s:end]
        seg = re.sub(r'^QUESTION \d+[\s\S]*$', '', seg, flags=re.M)
        marks = list(re.finditer(
            r'(Objection (\d+):|Obj\. (\d+):|_?On the contrary,?_?|'
            r'_?I answer that,?_?|Reply (?:to )?Obj(?:ection)?\.? ?(\d+)[:.])', seg))
        for k, mm in enumerate(marks):
            end2 = marks[k + 1].start() if k + 1 < len(marks) else len(seg)
            body = clean(seg[mm.end():end2])
            body = re.sub(r'(QUESTION \d+|[A-Z]+ ARTICLE).*$', '', body)
            token = mm.group(1)
            if token.startswith(('Objection', 'Obj.')):
                key = (q, a, f'arg. {mm.group(2) or mm.group(3)}')
            elif 'contrary' in token:
                key = (q, a, 's. c.')
            elif 'answer' in token:
                key = (q, a, 'co.')
            else:
                key = (q, a, f'ad {mm.group(4)}')
            if len(body.split()) >= 3 and key not in out:
                out[key] = body
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--part', required=True, choices=sorted(PARTS))
    ap.add_argument('--ct', required=True)
    ap.add_argument('--english', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    prefix, work, label, tag, pg, title = PARTS[a.part]
    eng = parse_english(a.english, label)
    print(f'  english paragraphs parsed: {len(eng)}')
    counter, key_of = {}, {}
    for q, ar, lab, _t in CT.labeled_rows(a.ct, prefix):
        p = counter.get((q, ar), 0) + 1
        counter[(q, ar)] = p
        key_of[f'{q}.{ar}.{p}'] = (q, ar, lab)
    refs, lat = tess_refs(a.tess, tag)
    mapping = {}
    for ref, tail in refs:
        q, ar, lab = key_of[tail]
        if lab == 'ad arg.':
            lab = 'ad 1'
        key = (q, ar, lab)
        if key not in eng and ar == 0 and lab != 'pr.':
            key = (q, 1, lab)
        if key in eng:
            mapping[ref] = eng[key]
    ok = emit(a.out, f'la/{work}', refs, lat, mapping, {
        'sources': [{'translator': 'Fathers of the English Dominican Province',
                     'year': 1920,
                     'title': f'The Summa Theologica, {title} (Benziger)',
                     'publisher': f'Benziger Brothers (Project Gutenberg #{pg})',
                     'mode': 'paragraph-exact',
                     'ref_composition': ['question', 'article', 'paragraph'],
                     'source_url': f'https://www.gutenberg.org/ebooks/{pg}'}],
        'license': 'Public domain: English Dominican Fathers translation, '
                   'second and revised edition 1920 to 1922; first edition 1911 to 1925.',
        'attribution': 'Fathers of the English Dominican Province, via Project Gutenberg'})
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
