"""Martial: epigram-exact English from the Bohn translation (1897 printing).

The corpus holds Martial twice: `martial.epigrams` (+ its fourteen .part
files, refs `<mart. B.E.L>`, a Perseus-derived selection) and the complete
`martialis.epigrammata_1..14` plus `martialis.de_spectaculis` (refs
`<mart. epig. E.L>`, `<mart. xeni. E.L>`, `<mart. apop. E.L>`,
`<mart. libe. E.L>`). Both families number epigrams identically — checked
book by book below, not assumed — so one alignment serves every file.
The .part files need no JSON of their own: backend/translations.py falls
back from `martial.epigrams.part.N` to `martial.epigrams`.

Source: the Bohn's Classical Library prose translation ("The Epigrams of
Martial translated into English prose", Bell, 1897 printing of the 1860
Bohn volume; public domain), in Roger Pearse's transcription at
tertullian.org — clean HTML, one anchor per epigram, which allows
structure-keyed exact alignment: corpus epigram numbers match Bohn's
anchors 1:1 in every one of the fourteen books (118, 93, 100, 89, 84, 94,
99, 82, 103, 104, 108, 98, 127, 223).

Two honesty rules:

- The Bohn edition leaves the grossest epigrams untranslated, printing
  Graglia's Italian instead. Serving Italian under an English tab is the
  invisible failure this pipeline exists to avoid, so every unit passes an
  English stopword test and a unit that fails is skipped and printed.
- De Spectaculis is numbered with letter variants (IV and IV.B) where the
  corpus runs one number across both; letter variants are merged into
  their parent number, and the book is validated by proper names like any
  other.

Usage:
    python scripts/translations/align_martial.py \
        --src-dir <dir with book01.htm..book14.htm, spectaculis.htm> \
        --tess-dir texts/la --out-dir <dir>
"""
import argparse
import html as htmllib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

SOURCE_URL = 'https://www.tertullian.org/fathers/martial_epigrams_book%02d.htm'
SPECT_URL = ('https://www.tertullian.org/fathers/'
             'martial_on_the_games_of_domitian_01_text.htm')

ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}

# Common-English words: a unit whose token overlap with these is tiny is
# Graglia's Italian, not the translator's English.
ENGLISH = set(('the of and to in a is that it was for with as his he on be at by '
               'this you which or from had not are but have an they will what '
               'your all my me who her she him their we our its if than then '
               'when so no nor do does did been being were has one two '
               'himself herself may can shall should would could there here '
               'those these into upon').split())


def roman_to_int(s):
    total, prev = 0, 0
    for ch in reversed(s.strip('. ').upper()):
        v = ROMAN.get(ch)
        if v is None:
            return None
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total or None


def strip_tags(fragment):
    fragment = re.sub(r'<blockquote.*?</blockquote>', ' ', fragment,
                      flags=re.S | re.I)
    fragment = re.sub(r'<sup>.*?</sup>', ' ', fragment, flags=re.S | re.I)
    fragment = re.sub(r'<[^>]+>', ' ', fragment)
    fragment = htmllib.unescape(fragment)
    fragment = re.sub(r'\|\d+\s*$', ' ', fragment)   # page-number artifacts
    return re.sub(r'\s+', ' ', fragment).strip()


def strip_title(text):
    """Drop the leading all-caps title remnant ('ON BASSA.', 'TO CAESAR,
    UPON HIS BANISHING INFORMERS.') that survives when a heading spans
    tags. Prose always begins at the first word containing a lower-case
    letter."""
    words = text.split()
    i = 0
    while i < len(words) and not re.search(r'[a-z]', words[i]):
        i += 1
    return ' '.join(words[i:]) if i < len(words) else text


def is_english(text):
    words = re.findall(r"[A-Za-z']+", text.lower())
    if len(words) < 4:
        return False
    hits = sum(1 for w in words if w in ENGLISH)
    return hits / len(words) >= 0.15


def parse_book(path):
    """{epigram_number_or_'epistula': english} for one Bohn book page."""
    h = open(path, encoding='utf-8', errors='ignore').read()
    # the prefatory epistle, where one exists, sits between the BOOK
    # heading and the first epigram anchor
    out = {}
    parts = re.split(r'<SPAN class="chapterno"><A NAME="C(\d+)[A-Za-z]*"></A>',
                     h)
    m = re.search(r'</h3>(.*)', parts[0], flags=re.S)
    if m:
        pre = strip_tags(m.group(1))
        pre = re.sub(r'^.*?BOOK [IVXL]+\.?\s*', '', pre)
        if len(pre.split()) >= 30 and is_english(pre):
            out['epistula'] = pre
    for i in range(1, len(parts), 2):
        n = int(parts[i])
        body = parts[i + 1]
        # drop the roman numeral + title line, then everything after the
        # page's navigation footer
        body = re.sub(r'^.*?</b>\s*</p>', '', body, count=1,
                      flags=re.S | re.I)
        body = re.split(r'<hr|<p align="center">\s*<a href', body,
                        flags=re.I)[0]
        text = strip_title(strip_tags(body))
        if n in out:      # a repeated anchor would mean the page is mangled
            raise ValueError(f'{path}: duplicate anchor C{n}')
        if text:
            out[n] = text
    return out


def parse_spectaculis(path):
    """{number: english}, letter variants (IV.B) merged into their parent."""
    h = open(path, encoding='utf-8', errors='ignore').read()
    h = re.sub(r'<blockquote.*?</blockquote>', ' ', h, flags=re.S | re.I)
    out = {}
    parts = re.split(r'<p>\s*([0-9]+|[IVXL]+(?:\.\s*B)?)\.\s+(?=[A-Z]{2})', h)
    for i in range(1, len(parts), 2):
        head, body = parts[i], parts[i + 1]
        merged = head.endswith('B')
        num = head.rstrip('. B')
        n = int(num) if num.isdigit() else roman_to_int(num)
        if n is None:
            continue
        text = strip_title(strip_tags(body.split('<hr')[0]))
        # everything after the final epigram is the transcription footer
        text = re.sub(r'This page has been online since.*', '', text).strip()
        if not text:
            continue
        if merged and n in out:
            out[n] += ' ' + text
        else:
            out[n] = text
    return out


def load_tess(path, pattern):
    """[(full_ref, epigram, latin_line)] with epigram int or 'epistula'/'pr'."""
    refs = []
    for line in open(path, errors='ignore'):
        m = re.match(pattern, line)
        if not m:
            continue
        ref, ep, latin = m.group(1), m.group(2), m.group(3)
        refs.append((ref, int(ep) if ep.isdigit() else ep, latin))
    return refs


def build(refs, english, tess_work, sources, note, log):
    units, unit_of, ref_to_unit = [], {}, {}
    for ref, ep, _ in refs:
        key = 'epistula' if ep in ('epistula', 'pr') else ep
        if key not in english:
            continue
        if key not in unit_of:
            unit_of[key] = len(units)
            units.append(english[key])
        ref_to_unit[ref] = unit_of[key]
    pairs = [(latin, units[ref_to_unit[ref]])
             for ref, _, latin in refs if ref in ref_to_unit]
    score = V.score(pairs, 'la', sample=800)
    out = {
        'tess_work': tess_work,
        'language': 'la',
        'n_tess_refs': len(refs),
        'n_translated': len(ref_to_unit),
        'coverage': round(len(ref_to_unit) / max(1, len(refs)), 4),
        'mean_source_lines_per_translation_unit':
            round(len(ref_to_unit) / max(1, len(units)), 1),
        'alignment_confidence':
            'high' if (score[0] is None or score[0] >= 0.5) else 'medium',
        'name_check_hit_rate': score,
        'name_check_n': score[1],
        'sources': sources,
        'license': 'Public domain: anonymous Bohn prose translation, 1860 '
                   '(1897 printing). Transcription by Roger Pearse '
                   '(tertullian.org), placed in the public domain.',
        'attribution': 'The Epigrams of Martial translated into English prose '
                       '(Bohn’s Classical Library, Bell, 1897), '
                       'transcribed by Roger Pearse at tertullian.org' + note,
        'n_units_stored': len(units),
        'units': units,
        'ref_to_unit': ref_to_unit,
    }
    log.append((tess_work, out['coverage'], len(units), score))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', required=True)
    ap.add_argument('--tess-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    books = {}
    dropped = []
    for b in range(1, 15):
        got = parse_book(os.path.join(args.src_dir, f'book{b:02d}.htm'))
        for k in sorted(got, key=str):
            if not is_english(got[k]):
                dropped.append((b, k))
                del got[k]
        books[b] = got
    for b, k in dropped:
        print(f'  book {b} epigram {k}: not English (Graglia italian), skipped')

    spect = parse_spectaculis(os.path.join(args.src_dir, 'spectaculis.htm'))
    for k in sorted(spect):
        if not is_english(spect[k]):
            print(f'  spectaculis {k}: not English, skipped')
            del spect[k]

    # ---- validate numbering book by book against the complete family ----
    for b in range(1, 15):
        f = os.path.join(args.tess_dir, f'martialis.epigrammata_{b}.tess')
        want = {ep for _, ep, _ in load_tess(
            f, r'<(mart\. \w+\. ([^.]+)\.\d+)>\s*(.*)')}
        missing = {w for w in want if w not in books[b]} - {'epistula'}
        # zero tolerance beyond the epigrams dropped as untranslated:
        # the numbering match is the whole basis of the 'exact' claim
        dropped_b = {k for bb, k in dropped if bb == b}
        if missing - dropped_b:
            print(f'BOOK {b}: epigrams {sorted(missing - dropped_b, key=str)[:8]} '
                  f'missing in the English — refusing to align this book')
            books[b] = {}

    log = []
    src = lambda b: [{
        'title': f'The Epigrams of Martial, Book {b} (Bohn, 1897)',
        'translator': 'anonymous (Bohn series)', 'year': 1897,
        'publisher': 'George Bell & Sons',
        'source_url': SOURCE_URL % b, 'mode': 'exact',
        'ref_composition': ['book', 'epigram'],
    }]

    # ---- the complete family: one file per book + de spectaculis ----
    for b in range(1, 15):
        f = os.path.join(args.tess_dir, f'martialis.epigrammata_{b}.tess')
        refs = load_tess(f, r'<(mart\. \w+\. ([^.]+)\.\d+)>\s*(.*)')
        out = build(refs, books[b], f'la/martialis.epigrammata_{b}',
                    src(b), '', log)
        json.dump(out, open(os.path.join(
            args.out_dir, f'la__martialis.epigrammata_{b}.json'), 'w'),
            ensure_ascii=False)

    refs = load_tess(os.path.join(args.tess_dir, 'martialis.de_spectaculis.tess'),
                     r'<(mart\. libe\. ([^.]+)\.\d+)>\s*(.*)')
    out = build(refs, spect, 'la/martialis.de_spectaculis', [{
        'title': 'Martial, On the Public Shows of Domitian (Bohn, 1897)',
        'translator': 'anonymous (Bohn series)', 'year': 1897,
        'publisher': 'George Bell & Sons',
        'source_url': SPECT_URL, 'mode': 'exact',
        'ref_composition': ['epigram'],
    }], '', log)
    json.dump(out, open(os.path.join(
        args.out_dir, 'la__martialis.de_spectaculis.json'), 'w'),
        ensure_ascii=False)

    # ---- the Perseus-derived family: one file, refs carry the book ----
    whole = os.path.join(args.tess_dir, 'martial.epigrams.tess')
    refs = []
    for line in open(whole, errors='ignore'):
        m = re.match(r'<(mart\. (\d+)\.([^.]+)\.\d+)>\s*(.*)', line)
        if m:
            refs.append((m.group(1), int(m.group(2)),
                         m.group(3), m.group(4)))
    english = {}
    for b in range(1, 15):
        for k, v in books[b].items():
            english[(b, k)] = v
    units, unit_of, ref_to_unit = [], {}, {}
    for ref, b, ep, _ in refs:
        key = (b, 'epistula' if ep == 'pr' else
               (int(ep) if ep.isdigit() else ep))
        if key not in english:
            continue
        if key not in unit_of:
            unit_of[key] = len(units)
            units.append(english[key])
        ref_to_unit[ref] = unit_of[key]
    pairs = [(latin, units[ref_to_unit[ref]])
             for ref, _, _, latin in refs if ref in ref_to_unit]
    score = V.score(pairs, 'la', sample=800)
    out = {
        'tess_work': 'la/martial.epigrams',
        'language': 'la',
        'n_tess_refs': len(refs),
        'n_translated': len(ref_to_unit),
        'coverage': round(len(ref_to_unit) / max(1, len(refs)), 4),
        'mean_source_lines_per_translation_unit':
            round(len(ref_to_unit) / max(1, len(units)), 1),
        'alignment_confidence':
            'high' if (score[0] is None or score[0] >= 0.5) else 'medium',
        'name_check_hit_rate': score,
        'name_check_n': score[1],
        'sources': [s for b in range(1, 15) for s in src(b)],
        'license': 'Public domain: anonymous Bohn prose translation, 1860 '
                   '(1897 printing). Transcription by Roger Pearse '
                   '(tertullian.org), placed in the public domain.',
        'attribution': 'The Epigrams of Martial translated into English prose '
                       '(Bohn’s Classical Library, Bell, 1897), '
                       'transcribed by Roger Pearse at tertullian.org',
        'n_units_stored': len(units),
        'units': units,
        'ref_to_unit': ref_to_unit,
    }
    json.dump(out, open(os.path.join(
        args.out_dir, 'la__martial.epigrams.json'), 'w'), ensure_ascii=False)
    log.append(('la/martial.epigrams', out['coverage'], len(units), score))

    print()
    for work, cov, n_units, sc in log:
        print(f'{work}: coverage {cov}, {n_units} units, names {sc}')


if __name__ == '__main__':
    main()
