#!/usr/bin/env python3
"""Sweep the server's citation builder over every text in the corpus.

Issue #566: Search result cards and Corpus/String search used to build each
citation in the BROWSER by parsing the raw `.tess` line tag. Any text whose
tag was not in the frontend's hand-kept abbreviation tables came out as
debris -- `Ach..Tat..1.1.0`, `bohairic.i_corinthians.1.1`,
`septuaginta.tlg011.urn:cts:greekLit:tlg0527.tlg011.1st1K-1`. The author's
own sweep ran the real frontend formatters over the first, middle and last
tag of all 3,496 texts and found 1,551 broken on search cards and 634 in
Corpus search.

The fix moves citation-building to the server (`backend.utils.build_citation`,
used by backend/scorer.py's `_build_result_side`, `/api/corpus-search`, and
the hapax/rare-pairs location builders). This script reproduces the author's
sweep against THAT function directly -- not through any particular endpoint,
since every endpoint this issue touches now funnels through it -- over every
text in the corpus, so a future change to the lemma table, a new corpus
import, or an edge case in a filename cannot silently reintroduce the bug.

For every .tess file under texts/<language>/, it takes the first, middle and
last line tag (the raw content between < and >) and runs it through
build_citation(). A result fails if it contains:
    - a doubled dot ("..")                  -- an unmapped abbreviation
    - an underscore ("_")                    -- a raw file-id slug
    - "urn:"                                 -- a CTS URN that leaked through
    - "tlg0"                                 -- a raw TLG id
    - the text's own raw file id verbatim    -- the tag-parsing fallback debris

Target: zero failures over every text, in every language.

Usage:
    cd ~/tesserae-v6-dev && source venv/bin/activate
    python scripts/review/check_result_citations.py
    python scripts/review/check_result_citations.py --language grc
    python scripts/review/check_result_citations.py --verbose

Exits 0 when every check passes, 1 otherwise, and prints a summary either way.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.utils import build_citation  # noqa: E402

TEXTS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'texts')

# Forbidden substrings in a built citation (case-insensitive except the raw
# file id check, which is done separately so mixed-case filenames still
# catch -- see _raw_id_leaked below).
_FORBIDDEN_SUBSTRINGS = ('..', '_', 'urn:', 'tlg0')


def _iter_tags(filepath):
    """Yield the raw tag content (between < and >) of every tagged line in a
    .tess file, in file order. Never raises on a decode hiccup -- a corpus
    file with a stray byte must not stop the sweep; it just contributes no
    tags from the unreadable line."""
    tags = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line.startswith('<'):
                    continue
                end = line.find('>')
                if end <= 1:
                    continue
                tag = line[1:end].strip()
                if tag:
                    tags.append(tag)
    except Exception as e:
        print(f"  ! could not read {filepath}: {e}", file=sys.stderr)
    return tags


def _sample_tags(tags):
    """First, middle, and last -- deduplicated (a 1- or 2-line text should
    not be checked three times over the same tag)."""
    if not tags:
        return []
    n = len(tags)
    idxs = sorted({0, n // 2, n - 1})
    return [tags[i] for i in idxs]


def _raw_id_leaked(citation, filename):
    """True if the UNPROCESSED filename stem -- lowercase, underscores and
    all, exactly as it sits on disk -- shows up verbatim in the citation.
    This is what the old tag-parsing fallback produced on a miss (e.g. the
    work title rendered as the literal slug "i_corinthians" or
    "ex_agatharchidis_de_maris_erythraeo_libri_excerpta").

    Case-SENSITIVE and unprocessed on purpose: `build_citation` legitimately
    title-cases a one-component filename into its own display form (a
    filename like "helias.tess", with no separate work segment, is author
    and title both -- "Helias, Helias 1" -- not a leak), so comparing against
    the exact on-disk spelling, not a case-folded one, is what tells a real
    slug leak apart from a correctly capitalized coincidence.
    """
    stem = filename[:-5] if filename.endswith('.tess') else filename
    return stem in citation


def check_citation(filename, ref, citation):
    """Return a list of reasons `citation` fails, empty if it's clean."""
    reasons = []
    low = citation.lower()
    for bad in _FORBIDDEN_SUBSTRINGS:
        if bad in low:
            reasons.append(f"contains {bad!r}")
    if _raw_id_leaked(citation, filename):
        reasons.append("contains the raw file id verbatim")
    if not citation.strip():
        reasons.append("empty")
    return reasons


def sweep(languages=None, verbose=False):
    if not os.path.isdir(TEXTS_ROOT):
        print(f"No texts/ directory found at {TEXTS_ROOT}", file=sys.stderr)
        return 1

    langs = languages or sorted(
        d for d in os.listdir(TEXTS_ROOT) if os.path.isdir(os.path.join(TEXTS_ROOT, d))
    )

    total_texts = 0
    total_checked = 0
    failures = []  # (language, filename, ref, citation, reasons)
    by_language_failed_texts = {}

    for lang in langs:
        lang_dir = os.path.join(TEXTS_ROOT, lang)
        if not os.path.isdir(lang_dir):
            print(f"  (skipping {lang}: no such directory)", file=sys.stderr)
            continue
        filenames = sorted(f for f in os.listdir(lang_dir) if f.endswith('.tess'))
        for filename in filenames:
            total_texts += 1
            filepath = os.path.join(lang_dir, filename)
            tags = _iter_tags(filepath)
            samples = _sample_tags(tags)
            text_failed = False
            for ref in samples:
                total_checked += 1
                try:
                    citation = build_citation(filename, ref)
                except Exception as e:
                    citation = ''
                    failures.append((lang, filename, ref, f'<exception: {e}>', ['build_citation raised']))
                    text_failed = True
                    continue
                reasons = check_citation(filename, ref, citation)
                if reasons:
                    failures.append((lang, filename, ref, citation, reasons))
                    text_failed = True
                elif verbose:
                    print(f"  ok  {lang}/{filename}  {ref!r} -> {citation!r}")
            if text_failed:
                by_language_failed_texts.setdefault(lang, set()).add(filename)

    print()
    print(f"Texts swept: {total_texts}  |  tags checked: {total_checked}")
    print(f"Languages: {', '.join(langs)}")
    print()

    if failures:
        print(f"FAILED: {len(failures)} tag(s) across "
              f"{sum(len(v) for v in by_language_failed_texts.values())} text(s)")
        by_lang_counts = ', '.join(
            f"{lang} {len(texts)}" for lang, texts in sorted(by_language_failed_texts.items())
        )
        print(f"By language (texts affected): {by_lang_counts}")
        print()
        print("First 30 failures:")
        for lang, filename, ref, citation, reasons in failures[:30]:
            print(f"  [{lang}] {filename}  ref={ref!r}")
            print(f"      -> {citation!r}  ({'; '.join(reasons)})")
        if len(failures) > 30:
            print(f"  ... and {len(failures) - 30} more")
        return 1

    print("PASS: every sampled tag over every text built a clean citation "
          "(no doubled dot, underscore, CTS URN, TLG id, or raw file id).")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--language', action='append', dest='languages',
                         help='Limit the sweep to one language directory under texts/ '
                              '(repeatable). Default: every language directory present.')
    parser.add_argument('--verbose', action='store_true',
                         help='Print every sampled tag and its built citation, not just failures.')
    args = parser.parse_args()
    sys.exit(sweep(languages=args.languages, verbose=args.verbose))


if __name__ == '__main__':
    main()
