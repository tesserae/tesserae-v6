#!/usr/bin/env python3
# ruff: noqa: E741  (the corpus lines are called `l` in a dozen throwaway loops, as in the other scripts here)
"""Aristotle, eleven works in the Oxford translation (W. D. Ross, ed., 1908 to
1930) and Kenyon's Athenian Constitution (1891), aligned to our works at CHAPTER
level (the translators' `Part`, which is the chapter).

Works and translators (first publication, all 1930 or earlier): Categories and On
Interpretation (E. M. Edghill 1928), Prior Analytics (A. J. Jenkinson 1928),
Posterior Analytics (G. R. G. Mure 1928), Topics and Sophistical Refutations
(W. A. Pickard-Cambridge 1928), Physics (R. P. Hardie and R. K. Gaye 1930), On the
Heavens (J. L. Stocks 1922), Meteorology (E. W. Webster 1923), On the Parts of
Animals (William Ogle 1911), On Sense and the Sensible (J. I. Beare 1908), and
the Athenian Constitution (F. G. Kenyon 1891). On the Soul (J. A. Smith, 1931) is
NOT used: it was first published after 1930.

Source: the Internet Classics Archive (MIT) plain-text files of the public-domain
translations (classics.mit.edu/Aristotle/<name>.mb.txt, fetched at one request a
second), which head every chapter `Part <n>` under `BOOK <roman>` or `SECTION <n>`.
Our references of these works already number book and chapter first (`priora.1.5.2`,
`1.1`, `4.13.1.2`), so a reference takes the English of its chapter. The script
compares the count of English chapters per book with the count of ours and
REFUSES a work where they differ, since a shifted chapter number would put the
wrong English beside right Greek with every check blind.

    align_aristotle_oxford.py SRC_DIR OUT_DIR [--dry]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work, tail, finish, clean, roman_to_int, group_align   # noqa: E402

src_dir, out_dir = sys.argv[1:3]
dry = '--dry' in sys.argv


def parse(fn):
    """-> {(book or 0, part): text}; SECTION files carry continuous part numbers."""
    lines = open(os.path.join(src_dir, fn), encoding='utf-8', errors='replace').read().split('\n')
    seps = [i for i, l in enumerate(lines) if l.startswith('-----')]
    body = lines[seps[0] + 1:seps[-1]] if len(seps) >= 2 else lines
    book, part, buf, out = 0, None, [], {}

    def flush():
        if part is not None:
            out[(book, part)] = clean(' '.join(buf))
    for ln in body:
        m = re.match(r'^BOOK ([IVXL]+)\s*$', ln.strip())
        if m:
            flush()
            book, part, buf = roman_to_int(m.group(1)), None, []
            continue
        if re.match(r'^SECTION \d+\s*$', ln.strip()):
            continue
        m = re.match(r'^Part (\d+)\s*$', ln.strip())
        if m:
            flush()
            part, buf = int(m.group(1)), []
            continue
        if part is not None:
            buf.append(ln.strip())
    flush()
    return out


def nums(t):
    return tuple(int(x) for x in re.findall(r'\d+', t))


WORKS = [
    # stem, source files by ref prefix, key from tail, translator, year, title
    ('aristotle.categoriae', {'': 'categories.mb.txt'}, lambda t: (0, nums(t)[0]), 'Edgar Montague Edghill', 1928, 'Categories'),
    ('aristotle.de_interpretatione', {'': 'interpretation.mb.txt'}, lambda t: (0, nums(t)[0]), 'Edgar Montague Edghill', 1928, 'On Interpretation'),
    ('aristotle.analytica_priora', {'priora': 'prior.mb.txt', 'posteriora': 'posterior.mb.txt'},
     lambda t: nums(t.split('.', 1)[1])[:2], None, 1928, 'Prior and Posterior Analytics'),
    ('aristotle.topica', {'': 'topics.mb.txt'}, lambda t: nums(t)[:2], 'William Alexander Pickard-Cambridge', 1928, 'Topica'),
    ('aristotle.de_sophisticis_elenchis', {'': 'sophist_refut.mb.txt'}, lambda t: (0, nums(t)[0]), 'William Alexander Pickard-Cambridge', 1928, 'De Sophisticis Elenchis'),
    ('aristotle.physica', {'': 'physics.mb.txt'}, lambda t: nums(t)[:2], 'R. P. Hardie and R. K. Gaye', 1930, 'Physica'),
    ('aristotle.de_caelo', {'': 'heavens.mb.txt'}, lambda t: nums(t)[:2], 'John Leofric Stocks', 1922, 'De Caelo'),
    ('aristotle.meteorologica', {'': 'meteorology.mb.txt'}, lambda t: nums(t)[:2], 'Edwin Wallace Webster', 1923, 'Meteorologica'),
    ('aristotle.de_partibus_animalium', {'': 'parts_animals.mb.txt'}, lambda t: nums(t)[:2], 'William Ogle', 1911, 'De Partibus Animalium'),
    ('aristotle.de_sensu_et_sensibilibus', {'': 'sense.mb.txt'}, lambda t: (0, nums(t)[0]), 'John Isaac Beare', 1908, 'De Sensu et Sensibilibus'),
    ('aristotle.constitution', {'': 'athenian_const.mb.txt'}, lambda t: (0, nums(t)[0]), 'Frederic George Kenyon', 1891, 'Athenaion Politeia'),
]
TRANSL = {'Prior': ('Arthur John Jenkinson', 'Prior Analytics'), 'Post': ('George Raleigh Gilson Mure', 'Posterior Analytics')}
cache = {}
for stem, files, keyf, translator, year, title in WORKS:
    refs, src, _ = load_work('grc', stem)
    eng = {}
    for pre, fn in files.items():
        if fn not in cache:
            cache[fn] = parse(fn)
        for k, v in cache[fn].items():
            eng[(pre, k)] = v
    units, idx, ref_to_unit = [], {}, {}
    ours_keys, unpaired = set(), 0
    for r in refs:
        t = tail(r)
        pre = t.split('.', 1)[0] if '' not in files else ''
        if pre not in files:
            unpaired += 1
            continue
        try:
            k = keyf(t)
        except (IndexError, ValueError):
            unpaired += 1
            continue
        if stem == 'aristotle.constitution' and not t[0].isdigit():
            unpaired += 1
            continue
        ours_keys.add((pre, tuple(k)))
        text = eng.get((pre, tuple(k)))
        if not text or len(text) < 40:
            unpaired += 1
            continue
        if (pre, tuple(k)) not in idx:
            idx[(pre, tuple(k))] = len(units)
            units.append(text)
        ref_to_unit[r] = idx[(pre, tuple(k))]
    en_keys = set(eng)
    o_by_book, e_by_book = {}, {}
    for pre, k in ours_keys:
        o_by_book[(pre, k[0])] = max(o_by_book.get((pre, k[0]), 0), k[-1])
    for pre, k in en_keys:
        e_by_book[(pre, k[0])] = max(e_by_book.get((pre, k[0]), 0), k[-1])
    diff = {b: (o_by_book[b], e_by_book.get(b)) for b in o_by_book if o_by_book[b] != e_by_book.get(b)}
    print(f'{stem}: our chapters per book vs English {"agree" if not diff else "DISAGREE " + str(diff)}; {unpaired} refs unpaired')
    merged = {}                       # (prefix, book, ours last chapter) -> English chapter numbers it takes
    if diff:
        # Only a difference that sits at the END of a book is repaired: the chapters before it must
        # pair one to one by length (group_align) and the last group alone may join two chapters on
        # one side. Anything else is refused: a shift in the middle of a book would put wrong English
        # beside right Greek in every chapter after it.
        fixed = True
        for (pre, bk) in diff:
            g_ch = sorted({k[-1] for p0, k in ours_keys if p0 == pre and k[0] == bk})
            e_ch = sorted(k[-1] for p0, k in en_keys if p0 == pre and k[0] == bk)
            gl = {c: 0 for c in g_ch}
            for r in refs:
                t = tail(r)
                p0 = t.split('.', 1)[0] if '' not in files else ''
                try:
                    kk = keyf(t)
                except (IndexError, ValueError):
                    continue
                if p0 == pre and kk[0] == bk and kk[-1] in gl:
                    gl[kk[-1]] += len(src[r])
            groups = group_align([gl[c] for c in g_ch], [len(eng[(pre, (bk, c))]) for c in e_ch])
            odd = [(a, b) for a, b in groups if len(a) != 1 or len(b) != 1]
            if odd and not (groups[-1] == odd[-1] and len(odd) == 1 and groups[-1][0][-1] == len(g_ch) - 1):
                print(f'   refusing {stem} book {bk or ""}: the chapters do not pair one to one up to the end of the book: {odd}')
                fixed = False
                break
            for a, b in groups:
                if len(a) == 1 and len(b) == 1:
                    merged[(pre, bk, g_ch[a[0]])] = [e_ch[b[0]]]
                else:
                    for gi in a:
                        merged[(pre, bk, g_ch[gi])] = [e_ch[bj] for bj in b]
            print(f'   {stem} book {bk or ""}: chapter counts differ {diff[(pre, bk)]}; the last Greek chapter(s) {[g_ch[i] for i in groups[-1][0]]} take English {[e_ch[j] for j in groups[-1][1]]}; earlier chapters pair one to one by length')
        if not fixed:
            continue
        # rebuild the unit list with the merges
        units, idx, ref_to_unit = [], {}, {}
        for r in refs:
            t = tail(r)
            pre = t.split('.', 1)[0] if '' not in files else ''
            if pre not in files:
                continue
            try:
                k = tuple(keyf(t))
            except (IndexError, ValueError):
                continue
            if stem == 'aristotle.constitution' and not t[0].isdigit():
                continue
            bk, ch = k[0], k[-1]
            parts = merged.get((pre, bk, ch), [ch])
            texts = [eng.get((pre, (bk, c)), '') for c in parts]
            text = ' '.join(x for x in texts if x)
            if len(text) < 40:
                continue
            key2 = (pre, bk, tuple(parts))
            if key2 not in idx:
                idx[key2] = len(units)
                units.append(text)
            ref_to_unit[r] = idx[key2]
    tr = translator or '; '.join(f'{v[0]} ({k.lower()})' for k, v in TRANSL.items())
    finish('grc', stem, units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='chapter',
           attribution=f'{tr}, {title}, in The Works of Aristotle translated into English under the editorship of W. D. Ross (Oxford: Clarendon Press); text from the Internet Classics Archive' if stem != 'aristotle.constitution'
           else 'Frederic G. Kenyon, Aristotle on the Constitution of Athens (London, 1891); text from the Internet Classics Archive',
           license=f'Public domain (published {year})',
           sources=[{'translator': tr, 'year': year, 'place': 'Oxford' if stem != 'aristotle.constitution' else 'London',
                     'publisher': 'Clarendon Press' if stem != 'aristotle.constitution' else 'Kegan Paul, Trench and Co.',
                     'title': title, 'mode': 'chapter', 'ref_composition': ['book', 'chapter'],
                     'url': 'http://classics.mit.edu/Aristotle/', 'pd_reason': f'published {year}'}],
           notes='Chapter-level units: every Greek line of a chapter shows the English of the whole chapter. '
                 f'{unpaired} references with no English chapter (headings, fragments, or a chapter the translation lacks) stay unpaired.')
