#!/usr/bin/env python3
"""Re-key Verity's Paradise Lost commentary to the corrected line numbers.

/home/ncoffee/tesserae-preview/data/commentaries/verity__milton.paradise_lost.json
is keyed inconsistently: some notes' `ref` follows Verity's own (correct)
line numbers, and some follow this corpus's old, wrong tags (e.g. the note
on "mortal" is filed at 1.3, though "Of that Forbidden Tree, whose mortal
tast" is line 1.2 in every edition; the note on "one greater Man" is
correctly at 1.4). scripts/corpus/renumber_paradise_lost.py's docstring and
the 2026-09-16 commit that fixed this corpus's own numbering both flagged
this without correcting it. Coordinator decision, 2026-09-16: correct it
here, in a copy, not in the source file (read only, never written to).

Rule, for a note with a lemma: take the lemma's first content word (the
first whitespace-separated token, skipping a leading token that is a short
function word -- see STOPWORDS -- since a lemma like "if he" or "Fast by"
is about "he" or "by", not the connective in front of it) and look for it,
case-insensitively and tolerant of this corpus's 1667/1674 spelling, in the
NEW (post-fix) corpus text at the note's CURRENT line, then at +/-1 line,
then +/-2, then +/-3 (checked in the order 0, -1, +1, -2, +2, -3, +3), each
line's words compared the same tolerant way. Two words match if they're
identical once lowercased and stripped to letters only (apostrophes and all
other punctuation removed), OR, if that fails, if their first five letters
match once stripped the same way -- deliberately loose, to bridge Verity's
modernized spelling against this corpus's old one (e.g. "fixed" vs "fixt"
does NOT match under either rule and is correctly one of the unresolved
notes; "necessitie" vs "necessity" DOES match on the first-five-letters
rule). The first line where a match turns up wins; the note's ref is
rewritten to that line. A note whose lemma matches nowhere in that seven-
line window keeps its current ref and is counted unresolved -- this script
never guesses further than that window. A note with no lemma (a range note
like "[1-6]") is never searched; its ref is kept as-is.

Output: a full copy of the input, with only `ref` fields changed, written
to verity__milton.paradise_lost.rekeyed.json next to this checkout's own
texts/ (NOT under any git-tracked directory -- do not commit this file;
only this script is committed). Usage:

    venv/bin/python scripts/corpus/rekey_verity_paradise_lost.py

Prints, in order: how many notes were kept (matched on their current
line), moved by +1, moved by -1, moved by some other offset, had no lemma
(never searched), and were unresolved; then, per book, the agreement rate
of the REKEYED file against the new text -- whether the first content word
is found ON the (possibly rekeyed) line, no +/-3 search this time, which is
the number that matters for judging the commentary's fit against this
corpus from here on.
"""
import json
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VERITY_PATH = '/home/ncoffee/tesserae-preview/data/commentaries/verity__milton.paradise_lost.json'
NEW_TESS_PATH = os.path.join(REPO_ROOT, 'texts', 'en', 'milton.paradise_lost.tess')
OUT_PATH = os.path.join(REPO_ROOT, 'verity__milton.paradise_lost.rekeyed.json')

REF_RE = re.compile(r'^Milton P\.L\. (\d+)\.(\d+)$')
TAG_RE = re.compile(r'^<Milton P\.L\. (\d+)\.(\d+)>\t(.*)$')
WORD_RE = re.compile(r"[A-Za-z']+")

STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'of', 'in', 'to', 'for', 'not', 'but',
    'with', 'from', 'this', 'that', 'was', 'were', 'are', 'his', 'her',
    'him', 'she', 'who', 'what', 'when', 'they', 'their', 'have', 'had',
    'has', 'on', 'as', 'by', 'at', 'if', 'so', 'is', 'it', 'be',
}

SEARCH_OFFSETS = (0, -1, 1, -2, 2, -3, 3)


def normalize_word(w):
    """Lowercase, letters only -- strips apostrophes and all other
    punctuation, per the module docstring's matching rule."""
    return re.sub(r'[^a-z]', '', w.lower())


def words_match(a, b):
    """a and b are already normalize_word()-ed. Exact match, or, failing
    that, first-five-letters match (the old-spelling tolerance)."""
    if not a or not b:
        return False
    if a == b:
        return True
    return a[:5] == b[:5]


def first_content_word(lemma):
    """The lemma's first content word, normalized -- skips one or more
    leading STOPWORDS tokens if a non-stopword token follows; falls back to
    the first normalized token at all if every token is a stopword; None if
    the lemma has no letters."""
    tokens = [normalize_word(t) for t in re.split(r'[\s\-]+', lemma.strip())]
    tokens = [t for t in tokens if t]
    if not tokens:
        return None
    for t in tokens:
        if t not in STOPWORDS:
            return t
    return tokens[0]


def load_new_text():
    """{(book, line): text} from the current (post-fix) whole-file .tess."""
    out = {}
    with open(NEW_TESS_PATH, encoding='utf-8') as f:
        for raw in f:
            m = TAG_RE.match(raw.rstrip('\n'))
            if not m:
                raise SystemExit(f'unexpected line in {NEW_TESS_PATH}: {raw!r}')
            out[(int(m.group(1)), int(m.group(2)))] = m.group(3)
    return out


def find_line(word, book, line, text_by_line):
    """Search SEARCH_OFFSETS around (book, line) for `word` (already
    normalized). Returns the matching offset, or None."""
    for offset in SEARCH_OFFSETS:
        text = text_by_line.get((book, line + offset))
        if text is None:
            continue
        if any(words_match(word, normalize_word(w)) for w in WORD_RE.findall(text)):
            return offset
    return None


def rekey(units, text_by_line):
    counts = {'no_lemma': 0, 'kept': 0, 'moved_+1': 0, 'moved_-1': 0, 'moved_other': 0, 'unresolved': 0}
    out = []
    for u in units:
        lemma = u.get('lemma')
        if not lemma:
            counts['no_lemma'] += 1
            out.append(u)
            continue
        m = REF_RE.match(u.get('ref') or '')
        if not m:
            counts['unresolved'] += 1
            out.append(u)
            continue
        book, line = int(m.group(1)), int(m.group(2))
        word = first_content_word(lemma)
        if word is None:
            counts['unresolved'] += 1
            out.append(u)
            continue
        offset = find_line(word, book, line, text_by_line)
        if offset is None:
            counts['unresolved'] += 1
            out.append(u)
        elif offset == 0:
            counts['kept'] += 1
            out.append(u)
        else:
            bucket = 'moved_+1' if offset == 1 else 'moved_-1' if offset == -1 else 'moved_other'
            counts[bucket] += 1
            nu = dict(u)
            nu['ref'] = f'Milton P.L. {book}.{line + offset}'
            out.append(nu)
    return out, counts


def agreement_by_book(units, text_by_line):
    """{book: [matched, total]} for lemma-bearing notes, checking ONLY the
    note's own (rekeyed) line -- no +/-3 search -- the number that reflects
    how well the rekeyed file now fits the new text at face value."""
    per_book = {}
    for u in units:
        lemma = u.get('lemma')
        if not lemma:
            continue
        m = REF_RE.match(u.get('ref') or '')
        if not m:
            continue
        book, line = int(m.group(1)), int(m.group(2))
        word = first_content_word(lemma)
        if word is None:
            continue
        text = text_by_line.get((book, line))
        matched = text is not None and any(
            words_match(word, normalize_word(w)) for w in WORD_RE.findall(text))
        mt = per_book.setdefault(book, [0, 0])
        mt[1] += 1
        if matched:
            mt[0] += 1
    return per_book


def main():
    with open(VERITY_PATH, encoding='utf-8') as f:
        verity = json.load(f)
    text_by_line = load_new_text()

    new_units, counts = rekey(verity['units'], text_by_line)

    print('rekey counts:')
    for key in ('kept', 'moved_+1', 'moved_-1', 'moved_other', 'no_lemma', 'unresolved'):
        print(f'  {key}: {counts[key]}')

    out = dict(verity)
    out['units'] = new_units
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'wrote {OUT_PATH}')

    print('\nVerity agreement per book, on the rekeyed file, against the new text:')
    per_book = agreement_by_book(new_units, text_by_line)
    total_m, total_t = 0, 0
    for book in sorted(per_book):
        m, t = per_book[book]
        total_m += m
        total_t += t
        print(f'  Book {book}: {m}/{t} = {m / t:.1%}')
    if total_t:
        print(f'  OVERALL: {total_m}/{total_t} = {total_m / total_t:.1%}')


if __name__ == '__main__':
    main()
