"""Philo Judaeus: section-exact Yonge English for the Greek treatises.

The corpus holds 28; 27 are written. On Joseph is in the registry but is
expected to fail validation and stay unwritten (see below).

Corpus refs are Cohn-Wendland section numbers, flat (`<philo_judaeus.
de_abrahamo 172>`) or book.section for the four multi-book works. C. D.
Yonge's complete translation (Bohn, 1854-55, public domain) as transcribed
at earlychristianwritings.com carries exactly those section numbers inline,
"(1) ... (2) ..." — and "(1.1)" with the book number for On Dreams — so
this is structure-keyed exact alignment, the same footing as Livy.

The Latin-title-to-Yonge-page mapping is hand-built and printed on every
run. Validation per work and per book: the corpus's section numbers must
be present in the parsed English (a book missing more than a twentieth is
refused), and every work passes the Greek proper-name check. On Joseph is
expected to fail and stay unwritten: the transcription drops its section
markers after (63) of 270, and two hundred sections served from one blind
blob is the kind of wrong this pipeline refuses.

Usage:
    python scripts/translations/align_philo.py \
        --src-dir <dir with book1.html..book40.html> \
        --tess-dir texts/grc --out-dir <dir>
"""
import argparse
import html as htmllib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

# corpus work -> [(corpus_book_or_None, yonge_page_number)]
MAPPING = {
    'de_opificio_mundi': [(None, 1)],
    'legum_allegoriarum_libri_iiii': [(1, 2), (2, 3), (3, 4)],
    'de_cherubim': [(None, 5)],
    'de_sacrificiis_abelis_et_caini': [(None, 6)],
    'quod_deterius_potiori_insidiari_soleat': [(None, 7)],
    'de_posteritate_caini': [(None, 8)],
    'de_gigantibus': [(None, 9)],
    'de_agricultura': [(None, 11)],
    'de_plantatione': [(None, 12)],
    'de_ebrietate': [(None, 13)],
    'de_sobrietate': [(None, 14)],
    'de_confusione_linguarum': [(None, 15)],
    'de_migratione_abrahami': [(None, 16)],
    'quis_rerum_divinarum_heres_sit': [(None, 17)],
    'de_congressu_eruditionis_gratia': [(None, 18)],
    'de_fuga_et_inventione': [(None, 19)],
    'de_mutatione_nominum': [(None, 20)],
    'de_somniis_lib_iii': [(1, 21), (2, 21)],   # (b.s) markers on one page
    'de_abrahamo': [(None, 22)],
    'de_josepho': [(None, 23)],                 # expected to fail validation
    'de_vita_mosis_lib_iii': [(1, 24), (2, 25)],
    'de_decalogo': [(None, 26)],
    'de_specialibus_legibus_lib_iiv': [(1, 27), (2, 28), (3, 29), (4, 30)],
    'de_virtutibus': [(None, 31)],
    'de_praemiis_et_poenis_et_de_exsecrationibus': [(None, 32)],
    'de_aeternitate_mundi': [(None, 35)],
    'in_flaccum': [(None, 36)],
    'legatio_ad_gaium': [(None, 40)],
}

YONGE_TITLES = {
    1: 'On the Creation', 2: 'Allegorical Interpretation I',
    3: 'Allegorical Interpretation II', 4: 'Allegorical Interpretation III',
    5: 'On the Cherubim', 6: 'On the Birth of Abel', 7: 'That the Worse is '
    'Wont to Attack the Better', 8: 'On the Posterity of Cain', 9: 'On the '
    'Giants', 11: 'On Husbandry', 12: "Concerning Noah's Work as a Planter",
    13: 'On Drunkenness', 14: 'On the Prayers and Curses of Noah',
    15: 'On the Confusion of Tongues', 16: 'On the Migration of Abraham',
    17: 'Who is the Heir of Divine Things?', 18: 'On Mating with the '
    'Preliminary Studies', 19: 'On Flight and Finding', 20: 'On the Change '
    'of Names', 21: 'On Dreams', 22: 'On Abraham', 23: 'On Joseph',
    24: 'On the Life of Moses I', 25: 'On the Life of Moses II',
    26: 'The Decalogue', 27: 'The Special Laws I', 28: 'The Special Laws II',
    29: 'The Special Laws III', 30: 'The Special Laws IV',
    31: 'On the Virtues', 32: 'On Rewards and Punishments',
    35: 'On the Eternity of the World', 36: 'Flaccus',
    40: 'On the Embassy to Gaius',
}


def page_text(path):
    h = open(path, encoding='utf-8', errors='ignore').read()
    m = re.search(r'The Works of Philo', h)
    if m:
        h = h[m.end():]
    t = re.sub(r'<[^>]+>', ' ', h)
    t = htmllib.unescape(t)
    t = re.sub(r'\{[^}]*\}', ' ', t)          # transcription footnotes
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'\bGo to the Table of Contents.*', '', t)
    return t


MARK = re.compile(r'\((\d+)(?:\.(\d+))?\)')


def clean_unit(text):
    text = re.sub(r'\b[IVXLC]+\.\s', ' ', text)   # chapter numerals
    return re.sub(r'\s+', ' ', text).strip()


def sections_of_page(text):
    """{(book_or_None, section): body} from (n) / (b.n) markers,
    monotonic per book with a short resync."""
    marks = []
    prev = {}
    for m in MARK.finditer(text):
        if m.group(2) is not None:
            bk, n = int(m.group(1)), int(m.group(2))
        else:
            bk, n = None, int(m.group(1))
        p = prev.get(bk, 0)
        if n == p + 1 or (p + 1 < n <= p + 3) or (n == 1 and bk not in prev):
            marks.append((bk, n, m))
            prev[bk] = n
    out = {}
    for i, (bk, n, m) in enumerate(marks):
        end = marks[i + 1][2].start() if i + 1 < len(marks) else len(text)
        body = clean_unit(text[m.end():end])
        if len(body.split()) >= 3:
            out[(bk, n)] = body
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', required=True)
    ap.add_argument('--tess-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    print('corpus work -> Yonge page mapping:')
    for work, pages in MAPPING.items():
        print(f'  {work} -> ' + ', '.join(
            f'book{p} ({YONGE_TITLES[p]})' + (f' as book {b}' if b else '')
            for b, p in pages))
    print()

    pages = {}
    for work, plist in MAPPING.items():
        for _, p in plist:
            if p not in pages:
                pages[p] = sections_of_page(
                    page_text(os.path.join(args.src_dir, f'book{p}.html')))

    for work, plist in MAPPING.items():
        tess = os.path.join(args.tess_dir, f'philo_judaeus.{work}.tess')
        refs = []
        for line in open(tess, errors='ignore'):
            m = re.match(r'<(philo_judaeus\.%s (?:(\d+)\.)?(\d+))>\s*(.*)'
                         % re.escape(work), line)
            if m:
                refs.append((m.group(1),
                             int(m.group(2)) if m.group(2) else None,
                             int(m.group(3)), m.group(4)))
        english = {}
        for bk, p in plist:
            page = pages[p]
            for (mbk, s), t in page.items():
                if bk is None:
                    # single-book work: only unbooked (n) markers count
                    if mbk is None:
                        english[(None, s)] = t
                elif mbk == bk:
                    # (b.n) markers name their book (On Dreams)
                    english[(bk, s)] = t
                elif mbk is None and len(plist) > 1:
                    # multi-book work split one page per book (Moses,
                    # Special Laws): the page's plain (n) markers belong
                    # to the corpus book this page is registered under
                    english[(bk, s)] = t

        # per-book structural validation
        ok = True
        for bk in sorted({b for _, b, _, _ in refs}, key=str):
            want = {s for _, b, s, _ in refs if b == bk}
            have = {s for (b, s) in english if b == bk}
            missing = want - have
            if len(missing) > max(2, len(want) * 0.05):
                print(f'{work} book {bk}: {len(missing)} of {len(want)} '
                      f'sections missing in the English '
                      f'{sorted(missing)[:6]}... — refusing this book')
                english = {(b, s): t for (b, s), t in english.items()
                           if b != bk}
                if len({b for _, b, _, _ in refs}) == 1:
                    ok = False
            elif missing:
                print(f'  {work} book {bk}: sections {sorted(missing)} '
                      f'missing, left uncovered')
        if not ok:
            print(f'SKIPPED {work}')
            continue

        units, unit_of, ref_to_unit = [], {}, {}
        for ref, bk, s, _ in refs:
            key = (bk, s)
            if key not in english:
                continue
            if key not in unit_of:
                unit_of[key] = len(units)
                units.append(english[key])
            ref_to_unit[ref] = unit_of[key]
        if not ref_to_unit:
            print(f'SKIPPED {work}: nothing aligned')
            continue
        pairs = [(latin, units[ref_to_unit[ref]])
                 for ref, _, _, latin in refs if ref in ref_to_unit]
        score = V.score(pairs, 'grc', sample=500)
        if score[0] is not None and score[1] >= 10 and score[0] < 0.25:
            print(f'WITHDRAWN {work}: name check {score}')
            continue
        coverage = round(len(ref_to_unit) / len(refs), 4)
        out = {
            'tess_work': f'grc/philo_judaeus.{work}',
            'language': 'grc',
            'n_tess_refs': len(refs),
            'n_translated': len(ref_to_unit),
            'coverage': coverage,
            'mean_source_lines_per_translation_unit':
                round(len(ref_to_unit) / max(1, len(units)), 1),
            'alignment_confidence':
                'high' if (score[0] is None or score[0] >= 0.5) else 'medium',
            'name_check_hit_rate': score,
            'name_check_n': score[1],
            'sources': [{
                'title': f'{YONGE_TITLES[p]} (The Works of Philo Judaeus)',
                'translator': 'C. D. Yonge', 'year': 1855,
                'publisher': 'H. G. Bohn (via earlychristianwritings.com)',
                'source_url':
                    f'https://www.earlychristianwritings.com/yonge/'
                    f'book{p}.html',
                'mode': 'exact',
                'ref_composition': ['book', 'section'] if plist[0][0]
                                   else ['section'],
            } for _, p in plist],
            'license': 'Public domain: translation published 1854-55. '
                       'Transcription from earlychristianwritings.com.',
            'attribution': 'C. D. Yonge, The Works of Philo Judaeus '
                           '(Bohn, 1854-55), via earlychristianwritings.com',
            'n_units_stored': len(units),
            'units': units,
            'ref_to_unit': ref_to_unit,
        }
        json.dump(out, open(os.path.join(
            args.out_dir, f'grc__philo_judaeus.{work}.json'), 'w'),
            ensure_ascii=False)
        print(f'{work}: coverage {coverage}, {len(units)} units, '
              f'names {score}')


if __name__ == '__main__':
    main()
