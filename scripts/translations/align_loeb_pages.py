#!/usr/bin/env python3
"""Facing-page alignment of a Loeb translation to the verse passages our text holds.

USED FOR Heseltine's Petronius and Rouse's Apocolocyntosis (one Loeb volume, 1913).
Our corpus text of each holds only some passages of the work, the VERSE passages
(Petronius: 29 passages at chapters 5, 14.2, 15.9 ... 139.2; the Apocolocyntosis:
chapters 2, 4, 7, 12 and 15). Neither Loeb translation numbers its chapters on the
English page in the OCR, and Heseltine prints Petronius's verse as running prose, so
the usual route (a margin number or a running head naming the lines) does not exist.

WHAT EXISTS INSTEAD is the layout of every Loeb: the Latin page and its English
translation face each other, and the OCR text alternates Latin run, English run. So

  1. The OCR text is cut into blocks (separated by blank lines), each voted Latin or
     English by common-word density, and consecutive blocks of one language become a
     run. Short runs (a footnote, an apparatus line) are absorbed by the run around them.
  2. Each passage of ours is looked up in the Latin runs by its words (u/v, i/j and case
     folded, so Loeb's Buecheler spelling meets our text's). A passage may cross a page.
  3. The unit served for the passage is the English run that FOLLOWS each Latin run
     holding any of its lines. That is a whole page of English, so units are coarse
     (about 11 source lines per unit) and always contain the translation of the
     passage, plus the prose around it.

CHECKS. (a) Locate score: the share of the passage's words found in the Latin runs
chosen. A low share means the edition differs or the passage was not found, and the
passage is skipped. (b) Proper names: the names in the passage against the English.
Length correlation is not meaningful (every unit is a page) and is not reported.

Usage:
    python align_loeb_pages.py --scan SCAN.txt --tess TESS --ref-regex REGEX \\
        --group-by N --work la/petronius.satyricon --out OUT.json \\
        --start-after TEXT --stop-before TEXT
"""
import argparse
import json
import os
import re
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V  # noqa: E402

ENGLISH = set(('the of and to in a is that it was for with as his he on be at by this you which '
               'or from had not are but have an they will what your all my me who her she him '
               'their we our its if than then when so no nor do does did been were has one there '
               'these those into upon would could should them thus').split())
LATIN = set(('et est non quid qui quod in ad cum sed nec si me te se tibi mihi quae nam ut sic '
             'iam hoc haec ille ipse sum es sunt esse tu ego nunc per pro de ex ab quam quis tamen '
             'dum aut atque nil nihil cui quem eum eam id ei eo illa illi ille quo ubi tum tam '
             'mea meo meum tua tuo tuum nos vos vel enim autem ergo').split())


def vote(text):
    words = re.findall(r"[a-z']+", text.lower())
    if len(words) < 4:
        return None
    e = sum(1 for w in words if w in ENGLISH)
    lx = sum(1 for w in words if w in LATIN)
    if e == lx:
        return None
    return 'en' if e > lx else 'la'


def norm_words(text):
    t = text.lower().replace('v', 'u').replace('j', 'i')
    return re.findall(r'[a-z]{3,}', t)


def runs_of(lines, start_after, stop_before, la_head, en_head):
    """Cut the OCR text into pages at the running heads. A Loeb's Latin pages carry
    one head and its English pages another (Petronius: TITUS PETRONIUS ARBITER on the
    Latin page, SATYRICON on the English page), and the English page is the one that
    follows its Latin page. Returns [(kind, text)] in reading order."""
    text = '\n'.join(lines)
    a = text.find(start_after) if start_after else 0
    b = text.find(stop_before, a) if stop_before else len(text)
    text = text[a:b if b > 0 else len(text)]
    la_re, en_re = re.compile(la_head), re.compile(en_head)
    pages = []
    ls = text.split('\n')
    i = 0
    while i < len(ls):
        s = ls[i].strip()
        kind = 'la' if la_re.match(s) else ('en' if en_re.match(s) else None)
        if kind:
            # a head can be two lines ("THE SATYRICON OF" / "TITUS PETRONIUS ARBITER")
            j = i + 1
            if j < len(ls) and (la_re.match(ls[j].strip()) or en_re.match(ls[j].strip())) \
                    and ls[j].strip() != s:
                j += 1
            pages.append([kind, []])
            i = j
            continue
        if pages:
            pages[-1][1].append(ls[i])
        i += 1
    out = []
    for k, t in pages:
        body = '\n'.join(t)
        words = re.findall(r"[a-z']+", body.lower())
        e = sum(1 for w in words if w in ENGLISH)
        lx = sum(1 for w in words if w in LATIN)
        # a running head the OCR lost or garbled leaves the page typed wrongly; the
        # words on the page overrule the head when they clearly disagree
        if len(words) >= 150:
            if k == 'la' and e > 4 * lx:
                k = 'en'
            elif k == 'en' and lx > 4 * e:
                k = 'la'
        out.append((k, body))
    return out


def clean_english(text):
    keep = []
    for ln in text.split('\n'):
        s = ln.strip()
        if not s:
            continue
        if re.fullmatch(r'[\W\d]*[A-Z]?\d*\s*\d*[\W\d]*', s):      # page numbers, signatures
            continue
        if re.match(r'^(THE SATYRICON OF|TITUS PETRONIUS ARBITER|SATYRICON|APOCOLOCYNTOSIS|LUCIUS ANNAEUS SENECA)\s*$', s):
            continue
        keep.append(s)
    out = ' '.join(keep)
    out = re.sub(r'(\w)- (\w)', r'\1\2', out)
    return re.sub(r'\s+', ' ', out).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scan', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--ref-regex', required=True, help='regex with groups: ref, group-key, text')
    ap.add_argument('--work', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--start-after', default='')
    ap.add_argument('--stop-before', default='')
    ap.add_argument('--latin-head', required=True)
    ap.add_argument('--english-head', required=True)
    ap.add_argument('--source-json', required=True, help='JSON file with the sources entry and licence fields')
    args = ap.parse_args()

    lines = open(args.scan, encoding='utf-8', errors='ignore').read().split('\n')
    runs = runs_of(lines, args.start_after, args.stop_before, args.latin_head, args.english_head)
    latin_idx = [i for i, (lab, _) in enumerate(runs) if lab == 'la']
    latin_words = {i: set(norm_words(runs[i][1])) for i in latin_idx}

    refs = []
    for line in open(args.tess, encoding='utf-8', errors='ignore'):
        m = re.match(args.ref_regex, line)
        if m:
            refs.append((m.group(1), m.group(2), m.group(3)))
    groups = OrderedDict()
    for ref, g, text in refs:
        groups.setdefault(g, []).append((ref, text))

    units, ref_to_unit, report = [], {}, []
    for g, items in groups.items():
        pw = norm_words(' '.join(t for _, t in items))
        if not pw:
            continue
        # Line by line: the Latin run that holds most of a line's words wins that
        # line, if it holds at least 60 percent of them and clearly more than the
        # next run. Common words (et, est, in) occur on every page, so a run is
        # chosen only by being the best home of some line, never by a pile of
        # shared common words.
        line_best = []
        covered_words, total_words = 0, 0
        for ref, ltext in items:
            lw = norm_words(ltext)
            if len(lw) < 2:
                continue
            total_words += len(lw)
            scored = sorted(((sum(1 for w in lw if w in latin_words[i]) / len(lw), i)
                             for i in latin_idx), reverse=True)
            top = scored[0]
            if top[0] >= 0.6:
                # every run within a hair of the best (a page the scan holds twice)
                line_best.extend(i for sc, i in scored if sc >= top[0] - 0.05)
                covered_words += int(top[0] * len(lw))
        chosen = sorted(set(line_best))
        locate = covered_words / max(1, total_words)
        # the English run that follows each chosen Latin run
        en = []
        for i in chosen:
            # the English page is the one right after its Latin page
            if i + 1 < len(runs) and runs[i + 1][0] == 'en' and (i + 1) not in en:
                en.append(i + 1)
        pieces = []
        for j in en:
            c = clean_english(runs[j][1])
            if c and c not in pieces:
                pieces.append(c)
        text = ' '.join(pieces)
        # Heseltine leaves some passages in Latin on the English page. A unit that
        # is not English, or that still holds the passage's own Latin words, is not
        # a translation of it and is skipped.
        uw = set(norm_words(text))
        leftover = sum(1 for w in pw if w in uw) / len(pw)
        words_t = re.findall(r"[a-z']+", text.lower())
        e_t = sum(1 for w in words_t if w in ENGLISH)
        l_t = sum(1 for w in words_t if w in LATIN)
        if text and (e_t < 3 * l_t or leftover >= 0.5):
            print(f'  passage {g}: the facing page is not English for it (leftover Latin {leftover:.2f}), skipped')
            report.append((g, len(items), round(locate, 2), len(chosen), 0))
            continue
        report.append((g, len(items), round(locate, 2), len(chosen), len(text)))
        if locate < 0.7 or not text:
            print(f'  passage {g}: locate score {locate:.2f}, skipped')
            continue
        uid = len(units)
        units.append(text)
        for ref, _ in items:
            ref_to_unit[ref] = uid
    # names are checked per passage (the whole passage against its unit)
    per = []
    for g, items in groups.items():
        r0 = items[0][0]
        if r0 in ref_to_unit:
            per.append((' '.join(t for _, t in items), units[ref_to_unit[r0]]))
    score = V.score(per, 'la', sample=500)
    src = json.load(open(args.source_json))
    out = {
        'tess_work': args.work, 'language': 'la',
        'n_tess_refs': len(refs), 'n_translated': len(ref_to_unit),
        'coverage': round(len(ref_to_unit) / len(refs), 4),
        'mean_source_lines_per_translation_unit': round(len(ref_to_unit) / max(1, len(units)), 1),
        'alignment_confidence': 'medium' if len(ref_to_unit) / len(refs) >= 0.9 else 'low',
        'name_check_hit_rate': score[0], 'name_check_n': score[1],
        'locate_scores': {g: loc for g, n, loc, k, ln in report},
        'verified_by': 'names',
        'sources': [src['source']], 'license': src['license'], 'attribution': src['attribution'],
        'n_units_stored': len(units), 'units': units, 'ref_to_unit': ref_to_unit,
    }
    json.dump(out, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'{args.work}: refs {len(refs)} translated {len(ref_to_unit)} coverage {out["coverage"]:.4f} '
          f'units {len(units)} names {score}')
    print('passages (group, lines, locate, latin runs, english chars):')
    for r in report:
        print('  ', r)


if __name__ == '__main__':
    main()
