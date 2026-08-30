#!/usr/bin/env python3
"""PD English for the batch-3 imports (Aquinas + Erasmus).

  summa    Summa Theologiae Ia, Fathers of the English Dominican Province
           (Benziger; PG #17611), PARAGRAPH-level exact: the English marks
           articles with bracketed loci "[I, Q. 1, Art. 1]" and paragraphs
           with "Objection N:", "_On the contrary,_", "_I answer that,_",
           "Reply Obj. N:"; these key one-to-one onto Corpus Thomisticum's
           TITLE labels (arg N / s. c. / co. / ad N), which is also how the
           .tess paragraph order was built (batch3_to_tess.parse_ct).
  moria    Praise of Folly, John Wilson 1668 (PG #9371): the English has no
           section numbers, so sections are served proportionally over the
           whole declamation with a name-check guard; the letter to More is
           in Wilson too and keyed separately.
  colloquia  Bailey 1725 (PG #30621): per-colloquy keyed by title, body
           proportional.

Usage: align_batch3.py --work summa --src <dir> --tess <file> --out <json>
"""
import argparse
import html as htmllib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'corpus'))
import proper_names as V
from batch3_to_tess import parse_ct


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


def tess_refs(path, prefix):
    refs, lat = [], {}
    pat = re.compile(r'^<(' + re.escape(prefix) + r'\s+([^>]+))>\s*(.*)')
    for line in open(path, encoding='utf-8', errors='replace'):
        m = pat.match(line)
        if m:
            refs.append((m.group(1), m.group(2)))
            lat[m.group(1)] = m.group(3)
    return refs, lat

# ------------------------------------------------------------------ summa

def parse_english_summa(path):
    """{(q, a, label): english} with labels matching Corpus Thomisticum's
    (arg N, s. c., co., ad N, and (q, 0, 'pr.') for question prologues)."""
    t = open(path, encoding='utf-8', errors='replace').read()
    t = t.split('*** START OF')[-1].split('*** END OF')[0]
    art = re.compile(r'\[I[.,]?\s*Q\.\s*(\d+),\s*Art\.\s*(\d+)\]')
    arts = [(m.start(), int(m.group(1)), int(m.group(2)))
            for m in art.finditer(t)]
    out = {}

    def clean(x):
        x = x.replace('_', ' ')
        x = re.sub(r'_{3,}', ' ', x)
        x = re.sub(r'\s+', ' ', x).strip()
        return x

    # question prologues: text between "QUESTION N" heading and the first
    # article marker of that question
    for m in re.finditer(r'^QUESTION (\d+)\s*$', t, flags=re.M):
        q = int(m.group(1))
        nxt = next((s for s, qq, aa in arts if s > m.end()), len(t))
        seg = t[m.end():nxt]
        # drop the ordinal-article heading line at the end of the segment
        seg = re.sub(r'\n[A-Z]+ ARTICLE\s*$', '', seg.rstrip())
        seg = re.sub(r'^\s*[A-Z, \'\?()0-9\n]+\n', '', seg)  # topic caps lines
        seg = re.sub(r'\(In \w+ Articles?\)', '', seg)
        body = clean(seg)
        if len(body.split()) >= 10:
            out[(q, 0, 'pr.')] = body

    for i, (s, q, a) in enumerate(arts):
        end = arts[i + 1][0] if i + 1 < len(arts) else len(t)
        seg = t[s:end]
        seg = re.sub(r'^QUESTION \d+[\s\S]*$', '', seg, flags=re.M)  # next q head
        marks = list(re.finditer(
            r'(Objection (\d+):|Obj\. (\d+):|_?On the contrary,?_?|'
            r'_?I answer that,?_?|Reply (?:to )?Obj(?:ection)?\.? ?(\d+)[:.])',
            seg))
        for k, mm in enumerate(marks):
            end2 = marks[k + 1].start() if k + 1 < len(marks) else len(seg)
            body = clean(seg[mm.end():end2])
            # trim trailing next-question/article heading residue
            body = re.sub(r'(QUESTION \d+|[A-Z]+ ARTICLE).*$', '', body)
            token = mm.group(1)
            if token.startswith(('Objection', 'Obj.')):
                num = mm.group(2) or mm.group(3)
                key = (q, a, f'arg. {num}')
            elif 'contrary' in token:
                key = (q, a, 's. c.')
            elif 'answer' in token:
                key = (q, a, 'co.')
            else:
                key = (q, a, f'ad {mm.group(4)}')
            if len(body.split()) >= 3:
                out[key] = body
    return out


def summa(src, tess, out):
    eng = parse_english_summa(os.path.join(
        src, 'aquinas', 'summa_english', 'pg17611_summa_part1_english.txt'))
    print(f'  english paragraphs parsed: {len(eng)}')
    rows = parse_ct(src)
    counter = {}
    key_of = {}
    for q, a, label, _text in rows:
        p = counter.get((q, a), 0) + 1
        counter[(q, a)] = p
        key_of[f'{q}.{a}.{p}'] = (q, a, label)
    refs, lat = tess_refs(tess, 'aquin. sth1a.')
    mapping = {}
    for ref, tail in refs:
        q, a, label = key_of[tail]
        label = label.rstrip()
        if label == 'ad arg.':
            label = 'ad 1'     # single-objection articles: English says Reply Obj. 1
        key = (q, a, label)
        if key not in eng and a == 0 and label != 'pr.':
            # single-article questions: CT omits 'a. 1', English prints Art. 1
            key = (q, 1, label)
        if key in eng:
            mapping[ref] = eng[key]
    return emit(out, 'la/aquinas.summa_theologiae_1', refs, lat, mapping, {
        'sources': [{'translator': 'Fathers of the English Dominican Province',
                     'year': 1911,
                     'title': 'The Summa Theologica, First Part (Benziger)',
                     'publisher': 'Benziger Brothers (Project Gutenberg #17611)',
                     'mode': 'paragraph-exact',
                     'ref_composition': ['question', 'article', 'paragraph'],
                     'source_url': 'https://www.gutenberg.org/ebooks/17611'}],
        'license': 'Public domain: English Dominican Fathers translation, '
                   'second and revised edition 1920; first edition 1911.',
        'attribution': 'Fathers of the English Dominican Province, '
                       'via Project Gutenberg'})


# ------------------------------------------------------------------ moria

def proportional_blocks(rows, english, block=6):
    out = {}
    n = len(rows)
    if n == 0 or not english:
        return out
    blocks = [rows[i:i + block] for i in range(0, n, block)]
    lat_lens = [sum(len(l) for _r, l in b) for b in blocks]
    total = sum(lat_lens) or 1
    sents = re.split(r'(?<=[.!?])\s+', english)
    sent_lens = [len(x) for x in sents]
    etotal = sum(sent_lens) or 1
    si = 0
    for bi, b in enumerate(blocks):
        target = lat_lens[bi] / total * etotal
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


def moria(src, tess, out):
    t = open(os.path.join(src, 'erasmus', 'praise_of_folly_wilson_pg9371.txt'),
             encoding='utf-8', errors='replace').read()
    t = t.split('*** START OF')[-1].split('*** END OF')[0]
    ep_start = t.find('THOMAS MORE, health:')
    body_head = t.find('An oration, of feigned matter')
    assert ep_start > 0 and body_head > ep_start

    def clean(x):
        x = x.replace('_', ' ')
        x = re.sub(r'\s+', ' ', x)
        return x.strip()

    epistle = clean(t[ep_start + len('THOMAS MORE, health:'):body_head])
    epistle = re.sub(r'THE PRAISE OF FOLLY\s*$', '', epistle).strip()
    body = clean(t[body_head:])
    body = re.sub(r'^An oration, of feigned matter,?\s*spoken by Folly in her'
                  r' own person\s*', '', body)
    body = re.sub(r"(THE END|End of the Project Gutenberg).*$", '', body)
    refs, lat = tess_refs(tess, 'erasm. moria.')
    pr_rows = [(r, lat[r]) for r, tail in refs if tail.startswith('pr.')]
    body_rows = [(r, lat[r]) for r, tail in refs if not tail.startswith('pr.')]
    mapping = {}
    # block=12: measured on the name check (6 -> 0.74, 12 -> 0.84, 20 -> 0.86); the
    # oration has no section numbers on the English side, so allocation is
    # proportional, re-anchored only at the epistle/oration boundary
    mapping.update(proportional_blocks(pr_rows, epistle, block=6))
    mapping.update(proportional_blocks(body_rows, body, block=12))
    return emit(out, 'la/erasmus.moriae_encomium', refs, lat, mapping, {
        'sources': [{'translator': 'John Wilson', 'year': 1668,
                     'title': 'The Praise of Folly',
                     'publisher': 'Project Gutenberg #9371',
                     'mode': 'proportional',
                     'ref_composition': ['whole work'],
                     'source_url': 'https://www.gutenberg.org/ebooks/9371'}],
        'license': 'Public domain: Wilson, 1668.',
        'attribution': 'John Wilson (1668), via Project Gutenberg'})


# -------------------------------------------------------------- colloquia

# corpus colloquy number -> Bailey Vol. I title (underscore-italic heading).
# The six absent from Vol. I (Charon, Peregrinatio, Funus, Coniugium impar,
# Cyclops, Epicureus) exist only in Bailey's Vol. II (never digitized) or in
# Tudor-spelling versions; left uncovered rather than shipped unreadable.
BAILEY = {
    1: 'The SHIPWRECK',
    2: 'The ABBOT and LEARNED WOMAN',
    6: 'The RELIGIOUS TREAT',
    7: 'The EXORCISM or APPARITION',
    8: 'The ALCHYMIST',
    9: 'DIVERSORIA',
    10: 'The SOLDIER and CARTHUSIAN',
    11: 'A LOVER and MAIDEN',
    13: 'The UNEASY WIFE',
    14: 'The LYING-IN WOMAN',
    15: 'The YOUNG MAN and HARLOT',
    17: 'An ENQUIRY concerning FAITH',
}


def colloquia(src, tess, out):
    t = open(os.path.join(src, 'erasmus', 'colloquies_bailey_vol1_pg14031.txt'),
             encoding='utf-8', errors='replace').read()
    t = t.split('*** START OF')[-1].split('*** END OF')[0]
    # colloquies head as _The SHIPWRECK._ ; find every underscore-title line
    heads = [(m.start(), m.group(1)) for m in
             re.finditer(r'^_([A-Za-z][^_\n]{4,60})\._?\s*$', t, flags=re.M)]

    def norm(x):
        return re.sub(r'[^a-z]', '', x.lower())

    english = {}
    for num, title in BAILEY.items():
        pos = [s_ for s_, h in heads if norm(h) == norm(title)]
        if not pos:
            print(f'  colloquy {num} "{title}": heading NOT FOUND')
            continue
        start = pos[-1]         # the ToC lists titles too; the body is last
        nxt = min((s_ for s_, _h in heads if s_ > start), default=len(t))
        seg = t[start:nxt]
        # drop the editorial ARGUMENT block (ends at the speaker line or the
        # first _Xx._ speaker tag)
        m = re.search(r'The ARGUMENT\.?', seg)
        if m:
            m2 = re.search(r'^_[A-Z][a-z]{1,6}\._', seg[m.end():], flags=re.M)
            if m2:
                seg = seg[m.end() + m2.start():]
        seg = seg.replace('_', ' ')
        seg = re.sub(r'\s+', ' ', seg).strip()
        english[num] = seg
    refs, lat = tess_refs(tess, 'erasm. colloq.')
    by_n = {}
    for ref, tail in refs:
        by_n.setdefault(int(tail.split('.')[0]), []).append((ref, lat[ref]))
    mapping = {}
    for n, rows in by_n.items():
        if n in english:
            mapping.update(proportional_blocks(rows, english[n], block=8))
    return emit(out, 'la/erasmus.colloquia', refs, lat, mapping, {
        'sources': [{'translator': 'Nathan Bailey', 'year': 1725,
                     'title': 'All the Familiar Colloquies of Erasmus, vol. I '
                              '(1878 reprint, ed. E. Johnson)',
                     'publisher': 'Project Gutenberg #14031',
                     'mode': 'colloquy-proportional',
                     'ref_composition': ['colloquy'],
                     'source_url': 'https://www.gutenberg.org/ebooks/14031'}],
        'license': 'Public domain: Bailey, 1725 (1878 reprint).',
        'attribution': 'N. Bailey (1725), via Project Gutenberg'})


WORKS = {'summa': summa, 'moria': moria, 'colloquia': colloquia}


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
