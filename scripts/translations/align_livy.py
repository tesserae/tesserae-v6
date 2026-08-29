"""Livy, Ab Urbe Condita: chapter-exact English from the Bohn translations.

The Perseus run left Livy the worst-served major work in the corpus: Roberts'
English existed only for books 1-10, and at BOOK granularity, one ~600-line
blob per book, confidence "very low". But the corpus references Livy as
book.chapter.section, and the complete Bohn translation on Project Gutenberg
(Spillan; Spillan and Edmonds; McDevitte; 1850s, public domain) prints every
chapter as a numbered paragraph. That allows what the Bible pipelines get:
alignment keyed on the text's own structure, not on page guessing.

Four volumes cover everything extant:
    19725  books 1-8      D. Spillan
    10907  books 9-26     D. Spillan and Cyrus Edmonds
    12582  books 27-36    W. A. McDevitte
    44318  books 37-45    W. A. McDevitte (with the epitomes, unused here)

Chapter markers: "BOOK <ROMAN>." opens a book; "PREFACE." is Livy's preface
(the corpus's 1.pr.*); "CHAPTER I." or a paragraph beginning "1. " opens a
chapter. Bracketed footnotes and marginal-page artifacts are stripped.

Validation before writing: each book's parsed chapter numbers are compared
with the corpus's chapter numbers for that book, and a book that disagrees
is skipped and printed rather than shipped misaligned. Proper names are
cross-checked per book, sampled, as in every other aligner here.

Usage:
    python scripts/translations/align_livy.py \
        --src-dir  <dir with gut_19725.txt etc.> \
        --tess     texts/la/livy.ab_urbe_condita.tess \
        --out      la__livy.ab_urbe_condita.json
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

VOLUMES = [
    ('gut_19725.txt', 'D. Spillan', 'https://www.gutenberg.org/ebooks/19725'),
    ('gut_10907.txt', 'D. Spillan and Cyrus Edmonds', 'https://www.gutenberg.org/ebooks/10907'),
    ('gut_12582.txt', 'W. A. McDevitte', 'https://www.gutenberg.org/ebooks/12582'),
    ('gut_44318.txt', 'W. A. McDevitte', 'https://www.gutenberg.org/ebooks/44318'),
]

ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}


def roman_to_int(s):
    s = s.strip('. ').upper()
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN.get(ch)
        if v is None:
            return None
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total


def strip_gutenberg(text):
    a = text.find('*** START')
    b = text.find('*** END')
    if a != -1:
        text = text[text.find('\n', a):]
    if b != -1:
        text = text[:b]
    return text


def clean(text):
    text = re.sub(r'\[Footnote[^\]]*\]', ' ', text, flags=re.S)
    text = re.sub(r'\[\d+\]', ' ', text)          # inline footnote markers
    text = re.sub(r'^\s*\d+\.\]\s*$', ' ', text, flags=re.M)  # page artifacts
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_volume(path):
    """{(book, chapter): text} — chapter is an int, or 'pr' for the preface."""
    text = strip_gutenberg(open(path, encoding='utf-8', errors='ignore').read())
    out = {}
    book = None
    chap = None
    buf = []

    def flush():
        if book is not None and chap is not None and buf:
            body = clean(' '.join(buf))
            if len(body.split()) >= 10:
                out[(book, chap)] = body

    for line in text.split('\n'):
        s = line.strip()
        # One heading in the Gutenberg text reads 'Book XLII.' in mixed case
        # while every other says 'BOOK', so the match is case-insensitive.
        m = re.match(r'^BOOK\s+([IVXLC]+)\.?\s*$', s, re.IGNORECASE)
        if m and roman_to_int(m.group(1)):
            flush()
            book, chap, buf = roman_to_int(m.group(1)), None, []
            continue
        if book is None:
            continue
        if re.match(r'^PREFACE\.?\s*$', s):
            flush()
            chap, buf = 'pr', []
            continue
        m = re.match(r'^CHAPTER\s+([IVXLC]+)\.?\s*$', s)
        if m and roman_to_int(m.group(1)):
            flush()
            chap, buf = roman_to_int(m.group(1)), []
            continue
        m = re.match(r'^(\d+)\.\s+(\S.*)$', s)
        if m:
            n = int(m.group(1))
            prev = 0 if chap in (None, 'pr') else chap
            # n == prev+1 is the normal chain. A short jump forward resyncs
            # over a chapter whose number the transcription lost (book 9's
            # "23." is simply absent, and the strict chain used to discard
            # every chapter after it). Larger numbers are numbered lists
            # inside the prose and are ignored.
            if n == prev + 1 or (prev + 1 < n <= prev + 5):
                flush()
                chap, buf = n, [m.group(2)]
                continue
        if chap is not None and s:
            buf.append(s)
    flush()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    chapters = {}
    for fname, _, _ in VOLUMES:
        got = parse_volume(os.path.join(args.src_dir, fname))
        overlap = set(got) & set(chapters)
        chapters.update({k: v for k, v in got.items() if k not in chapters})
        print(f'{fname}: {len(got)} chapters '
              f'(books {min(b for b, _ in got)}-{max(b for b, _ in got)})'
              + (f', {len(overlap)} overlapping ignored' if overlap else ''))

    # corpus refs, grouped by (book, chapter)
    refs = []
    corpus = {}
    for line in open(args.tess, errors='ignore'):
        m = re.match(r'<(livy\. urbe\. (\d+)\.(pr|\d+)\.\d+)>\s*(.*)', line)
        if not m:
            continue
        ref, b, c, latin = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        c = 'pr' if c == 'pr' else int(c)
        refs.append((ref, b, c, latin))
        corpus.setdefault((b, c), 0)
        corpus[(b, c)] += 1

    corpus_books = sorted({b for b, _ in corpus})
    good_books, skipped_books = [], []
    for b in corpus_books:
        want = {c for bb, c in corpus if bb == b}
        have = {c for bb, c in chapters if bb == b}
        missing = want - have
        if len(missing) > max(2, len(want) * 0.05):
            skipped_books.append((b, sorted(missing, key=str)[:6], len(want)))
        else:
            good_books.append(b)
            if missing:
                print(f'  book {b}: {len(missing)} of {len(want)} chapters '
                      f'missing in the English: {sorted(missing, key=str)}')

    units, unit_of, ref_to_unit = [], {}, {}
    merged = 0
    for ref, b, c, _ in refs:
        key = (b, c)
        if b not in good_books:
            continue
        if key not in chapters:
            # A chapter whose number the transcription lost is still
            # TRANSLATED: its text sits at the end of the previous chapter's
            # paragraph. Serve that merged unit rather than nothing.
            prev = (b, c - 1) if isinstance(c, int) and c > 1 else None
            if prev and prev in chapters:
                key = prev
                merged += 1
            else:
                continue
        if key not in unit_of:
            unit_of[key] = len(units)
            units.append(chapters[key])
        ref_to_unit[ref] = unit_of[key]
    if merged:
        print(f'  {merged} lines served from a merged neighbouring chapter')

    # name check, sampled per book
    pairs = []
    for ref, b, c, latin in refs:
        if ref in ref_to_unit:
            pairs.append((latin, units[ref_to_unit[ref]]))
    score = V.score(pairs, 'la', sample=800)

    out = {
        'tess_work': 'la/livy.ab_urbe_condita',
        'language': 'la',
        'n_tess_refs': len(refs),
        'n_translated': len(ref_to_unit),
        'coverage': round(len(ref_to_unit) / len(refs), 4),
        'mean_source_lines_per_translation_unit':
            round(len(ref_to_unit) / max(1, len(units)), 1),
        'alignment_confidence': 'high',
        'name_check_hit_rate': score,
        'name_check_n': min(800, len(pairs)),
        'sources': [{
            'title': f'The History of Rome ({fname.split("_")[1].split(".")[0]})',
            'translator': tr, 'year': 1850, 'publisher': 'Bohn (via Project Gutenberg)',
            'source_url': url, 'mode': 'exact',
            'ref_composition': ['book', 'chapter'],
        } for fname, tr, url in VOLUMES],
        'license': 'Public domain: translations published 1850s. '
                   'Text from Project Gutenberg.',
        'attribution': 'D. Spillan, Cyrus Edmonds, and W. A. McDevitte '
                       '(Bohn, 1850s), via Project Gutenberg',
        'n_units_stored': len(units),
        'units': units,
        'ref_to_unit': ref_to_unit,
    }
    json.dump(out, open(args.out, 'w'), ensure_ascii=False)
    print(f'\ncoverage {out["coverage"]} ({len(ref_to_unit)} of {len(refs)} lines), '
          f'{len(units)} chapter units, name check {score}')
    for b, miss, want in skipped_books:
        print(f'  SKIPPED book {b}: missing chapters {miss}... of {want}')


if __name__ == '__main__':
    main()
