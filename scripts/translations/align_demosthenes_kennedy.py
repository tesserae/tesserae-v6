#!/usr/bin/env python3
# ruff: noqa: E741  (the corpus lines are called `l` in a dozen throwaway loops, as in the other scripts here)
"""Demosthenes: the speeches, the Exordia and the Epistles that Charles Rann Kennedy
translated for Bohn's Classical Library (5 vols., 1852 to 1863), aligned to our
works at SPEECH level (one unit per speech, the Exordia by exordium, the letters by
letter).

Kennedy prints no section numbers, so a speech is the finest unit his English
gives. About thirty-six works in our corpus that no other public-domain English
covers (the Loeb volumes of 1935 to 1939 are in copyright) get their speech.

The danger of whole-speech units is that the plain name check is nearly blind: a
name from Against Androtion appears somewhere in a whole speech against
Androtion, but also in Against Timocrates, which attacks the same man. So every
speech is also run against ALL the English speeches (the rival test), but the
private speeches share litigants, so the margins are narrow and the rival test
cannot be the judge. What identifies a speech is Kennedy's printed title (the
headings are matched in order, each after the one before), and the three checks
that stand behind it are: the English to Greek length ratio of the whole speech
(0.8 to 2.4, which catches a mis-cut), the names (the paired English must score
at least 60 percent of the best other speech's score, and at least five), and
the plain name check (0.3 on at least seven names for a single unit). A speech
failing any of them is refused and reported.

Sources: Internet Archive OCR of volumes 3, 4 and 5 (orationsofdemos03demo,
04demo, 05demo; the 1878 printing of the Bohn text). Each speech opens with 'THE
ORATION AGAINST X' (the OCR garbles some of them, so the patterns are tolerant)
and runs to the next heading, the appendices or the index; Kennedy's own
'ARGUMENT' stays at the head of each unit, his running heads are dropped, and
words split at a line end are rejoined.

    align_demosthenes_kennedy.py SRC_DIR OUT_DIR [--dry]
SRC_DIR holds k03.txt, k04.txt and k05.txt.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V                                                    # noqa: E402
from chapter_common import (load_work, finish, clean, dehyphenate, drop_footnotes,   # noqa: E402
                            _is_running_head, split_chapters_fuzzy)

src_dir, out_dir = sys.argv[1:3]
dry = '--dry' in sys.argv


def norm(l):
    return re.sub(r'\s+', ' ', l).strip()


def load(fn):
    return open(os.path.join(src_dir, fn), encoding='utf-8', errors='replace').read().split('\n')


def find(lines, pat, after=0):
    for i in range(after, len(lines)):
        if re.search(pat, norm(lines[i])):
            return i
    raise ValueError(f'not found: {pat}')


# (volume file, first heading, [(our work, heading pattern)...], closing pattern)
VOLS = [
    ('k03.txt', [('demosthenes.against_midias', r'^THE ORATION AGAINST MIDIAS'),
                 ('demosthenes.against_androtion', r'^THE ORATION AGAINST ANDROTION'),
                 ('demosthenes.against_aristocrates', r'^THE ORATION AGAINST ARISTOCRATE')], r'^APPENDIX I\.'),
    ('k04.txt', [('demosthenes.against_timocrates', r'^THE ORATION AGAINST TIMOCRATES'),
                 ('demosthenes.against_aristogiton_1', r'^THE ORATION AGAINST ARISTOGITON\W+I\.'),
                 ('demosthenes.against_aristogiton_2', r'^THE ORATIO\w* AGAINST A\w{2}STOGIT\w+\W+II\.'),
                 ('demosthenes.against_aphobus_1', r'^THE ORATION AGAINST APHOBUS\W+[IL1]\.?$'),
                 ('demosthenes.against_aphobus_2', r'^THE ORATION AGAINST APHOBUS\W+(IL|II|11)'),
                 ('demosthenes.against_aphobus_3', r'^THE ORATION AGAINST APHOBUS\W+III'),
                 ('demosthenes.against_onetor_30', r'^THE ORATION AGAINST ONETOR\W+I\.'),
                 ('demosthenes.against_onetor_31', r'^THE ORATION AGAINST ONETOR\W+II'),
                 ('demosthenes.against_zenothemis', r'^THE ORATION AGAINST ZE\w+THEMIS'),
                 ('demosthenes.against_apatourius', r'^THE ORATION AGAINST APATURIUS'),
                 ('demosthenes.against_phormio', r'^THE ORATION AGAINST PHORMIO'),
                 ('demosthenes.against_lacritus', r'^THE ORATION AGAINST LACRITUS'),
                 ('demosthenes.for_phormio', r'^THE ORATIO\w* FOR PHORM'),
                 ('demosthenes.against_pantaenetus', r'^THE ORATION AGAINST PANT\W*NETUS'),
                 ('demosthenes.against_nausimachus_and_xenopeithes', r'^THE ORATION AGAINST NAUSIMACHUS'),
                 ('demosthenes.against_boeotus_1', r'^THE ORATION AGAINST B\w+TUS\W+I\.'),
                 ('demosthenes.against_boeotus_2', r'^THE ORATION AGA\w+ B\w+TUS\W+(II|11)'),
                 ('demosthenes.against_spudias', r'^THE ORATION AGAINST SPUDIAS'),
                 ('demosthenes.against_phaenippus', r'^THE ORATION AGAINST PH\W+NIPPUS')], r'^APPENDIX 1\.'),
    ('k05.txt', [('demosthenes.against_macartatus', r'^THE ORATION AGAINST MACARTATUS'),
                 ('demosthenes.against_leochares', r'^THE ORATION AGAINST LEOCHARES'),
                 ('demosthenes.against_stephanus_1', r'^(THE ORATION )?AGAINST STEPHANUS\W+I\.'),
                 ('demosthenes.against_stephanus_2', r'^THE ORATION AGAINST STEPHANUS\W+(II|IT|11)'),
                 ('demosthenes.against_evergus_and_mnesibulus', r'^ORATION AGAINST EUERGUS'),
                 ('demosthenes.against_olympiodorus', r'^THE ORATION AGAINST OLYMPIODORUS'),
                 ('demosthenes.against_timotheus', r'^THE ORATION AGAINST TIMOTHEUS'),
                 ('demosthenes.against_polycles', r'^THE ORATION AGAINST POLYCLES'),
                 ('demosthenes.on_the_trierarchic_crown', r'^THE ORATION FOR THE NAVAL CROWN'),
                 ('demosthenes.against_callippus', r'^THE ORATION AGAI\w+ CALLIPPUS'),
                 ('demosthenes.against_nicostratus', r'^THE ORATION AGAINST NICOST'),
                 ('demosthenes.against_conon', r'^THE ORATION AGAINST CONON'),
                 ('demosthenes.against_callicles', r'^THE ORATION AGAINST CALLICLES'),
                 ('demosthenes.against_dionysodorus', r'^THE ORATION AGAINST DIONYSODORUS'),
                 ('demosthenes.against_eubulides', r'^THE ORATION AGAINST EUBULIDES'),
                 ('demosthenes.against_theocrines', r'^THE ORATION AGAINST THEOCRINES'),
                 ('demosthenes.against_neaera', r'^THE \w+ AGAINST NE\W*ERA'),
                 ('demosthenes.funeral_speech', r'^THE FUNERAL ORATION\.'),
                 ('demosthenes.erotic_essay', r'^THE EROTIC ORATION\.')], r'^EXORDI'),
]
texts = {}                           # work -> (english text, volume)
for fn, heads, closing in VOLS:
    lines = load(fn)
    at, idx = 0, []
    for stem, pat in heads:
        at = find(lines, pat, at + 1 if idx else 0)
        idx.append((stem, at))
    stop = find(lines, closing, idx[-1][1] + 1)
    for k, (stem, a) in enumerate(idx):
        b = idx[k + 1][1] if k + 1 < len(idx) else stop
        seg = [l for l in lines[a + 1:b] if not _is_running_head(l) and not re.match(r'^\s*\d{1,3}\s*$', l)]
        texts[stem] = clean(dehyphenate('\n'.join(drop_footnotes(seg))))

# the Exordia and the Epistles (volume 5)
lines = load('k05.txt')
ea = find(lines, r'^EXORDI\W*A\.')
eb = find(lines, r'^THE EPISTLES\.', ea)
ex_lines = [l for l in lines[ea + 1:eb] if not _is_running_head(l) or re.match(r'^[IVXLC]+\.$', norm(l))]
# numeral-only lines ('XXVIII.') open an exordium: join them to the text that follows
joined = []
for i, l in enumerate(ex_lines):
    s = norm(l)
    if re.fullmatch(r'[IVXLC1l]{1,8}[.,]?', s) and i + 1 < len(ex_lines):
        ex_lines[i + 1] = s.rstrip('.,') + '. ' + ex_lines[i + 1].lstrip()
        continue
    joined.append(l)
exordia, ok_ex = split_chapters_fuzzy(joined, max_skip=3)
print(f'Exordia: {len(exordia)} read, last numeral {exordia[-1][0] if exordia else None}, chain ok {ok_ex}')
ea = find(lines, r'^EPISTLE I\.', eb)
ee = find(lines, r'^THE (KNB|END)', ea)
epistles, cur, buf = {}, None, []
seq = 0
for l in lines[ea:ee]:
    s = norm(l)
    m = re.match(r'^EPISTLE ([IVXL]+|IT|V1)\.?$', s)
    if m:
        if cur:
            epistles[cur] = clean(dehyphenate('\n'.join(drop_footnotes(buf))))
        seq += 1
        cur, buf = seq, []
        continue
    if cur and not _is_running_head(l) and not re.match(r'^\s*\d{1,3}\s*$', l):
        buf.append(l)
if cur:
    epistles[cur] = clean(dehyphenate('\n'.join(drop_footnotes(buf))))
print(f'Epistles read: {sorted(epistles)}')

# ---- the rival test across all English speeches -------------------------------------
pool_names = list(texts)
pool_stems = {k: V.english_stems(texts[k]) for k in pool_names}


def agree(lines_, stems):
    n = 0
    for l in lines_:
        for _, c in V.names_in(l, 'grc'):
            if any(e[:4] == c[:4] for e in stems):
                n += 1
                break
    return n


refused = []
for stem, text in sorted(texts.items()):
    refs, src, _ = load_work('grc', stem)
    if not refs:
        print(f'{stem}: no such text, skipped')
        continue
    mine = [src[r] for r in refs]
    sc = {k: agree(mine, pool_stems[k]) for k in pool_names}
    best_other = max((v for k, v in sc.items() if k != stem), default=0)
    ratio0 = len(text) / max(1, sum(len(l) for l in mine))
    wins = (sc[stem] >= 0.6 * best_other and sc[stem] >= 5 and 0.8 <= ratio0 <= 2.4)
    ratio = len(text) / max(1, sum(len(l) for l in mine))
    print(f'{stem:48s} own {sc[stem]:3d} best other {best_other:3d} English/Greek length {ratio:.2f} -> ' + ('wins' if wins else 'LOSES'))
    if not wins:
        refused.append(stem)
        continue
    units = [text]
    ref_to_unit = {r: 0 for r in refs}
    finish('grc', stem, units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='speech',
           min_names=7, extra_evidence='speech identified by Kennedy\'s printed title in order; length ratio English to Greek '
                                       f'{ratio0:.2f}; names {sc[stem]} against {best_other} for the best other speech',
           attribution='Charles Rann Kennedy, The Orations of Demosthenes (Bohn\'s Classical Library, 1852 to 1863); scans at the Internet Archive',
           license='Public domain (published 1852 to 1863)',
           sources=[{'translator': 'Charles Rann Kennedy', 'year': 1860, 'place': 'London', 'publisher': 'Henry G. Bohn',
                     'title': 'The Orations of Demosthenes, translated, 5 vols. (Bohn\'s Classical Library)',
                     'mode': 'speech', 'ref_composition': ['speech'],
                     'url': 'https://archive.org/details/orationsofdemos03demo (vols. 3 to 5)', 'pd_reason': 'published 1852 to 1863'}],
           notes='One unit for the whole speech, with Kennedy\'s argument at its head: his English carries no section numbers. '
                 f'Own-speech names {sc[stem]} against {best_other} for the best other speech.')
print('refused:', refused)

# exordia and epistles: unit per exordium / letter, only where the numeral chain is whole
for stem, prefix, pieces, pat in (('demosthenes.exordia', 'ex.', dict(exordia), r'ex\.\s*(\d+)\.(\d+)'),
                                  ('demosthenes.letters', 'L.', epistles, r'L\.\s*(\d+)\.(\d+)')):
    refs, src, _ = load_work('grc', stem)
    units, idx, r2u = [], {}, {}
    for r in refs:
        m = re.search(pat, r)
        if not m:
            continue
        k = int(m.group(1))
        if k in pieces:
            if k not in idx:
                idx[k] = len(units)
                units.append(pieces[k])
            r2u[r] = idx[k]
    if units:
        finish('grc', stem, units, r2u, refs, src, out_dir=out_dir, dry=dry, mode='exact', exact=True,
               attribution='Charles Rann Kennedy, The Orations of Demosthenes, vol. 5 (Bohn\'s Classical Library, 1863); scans at the Internet Archive',
               license='Public domain (published 1863)',
               sources=[{'translator': 'Charles Rann Kennedy', 'year': 1863, 'place': 'London', 'publisher': 'Henry G. Bohn',
                         'title': 'The Orations of Demosthenes, vol. 5: the Exordia and the Epistles',
                         'mode': 'exact', 'url': 'https://archive.org/details/orationsofdemos05demo', 'pd_reason': 'published 1863'}],
               notes='One unit per exordium or letter; the numeral chain of the OCR was followed with up to three lost markers.')
