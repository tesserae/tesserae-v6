#!/usr/bin/env python3
"""Part 1 step 2 for issue #580.

Takes twenty sample lines from files affected by the mark-before-capital
bug, builds the corrected version of each line (move the marks onto the
capital, apply NFC), and runs the production Greek tokenizer/lemmatizer
(backend.text_processor) on both the stored and corrected text. Reports
whether tokens and lemmas differ.
"""
import glob
import os
import random
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.text_processor import TextProcessor

COMBINING_RUN = r'[̀-ͯ]+'
GREEK_CAPITAL = r'[Α-ΩΆΈ-Ώ]'
PATTERN = re.compile(r'(?:(?<=[ \t])|^)(' + COMBINING_RUN + r')(' + GREEK_CAPITAL + r')', re.MULTILINE)

TAG_RE = re.compile(r'^(<[^>]*>)([ \t]*)')


def split_tag(line):
    m = TAG_RE.match(line)
    if m:
        return m.group(0), line[m.end():]
    return '', line


def fix_line(rest):
    def repl(m):
        marks, capital = m.group(1), m.group(2)
        return unicodedata.normalize('NFC', capital + marks)
    return PATTERN.sub(repl, rest)


def find_sample_lines(directory, n):
    files = sorted(glob.glob(os.path.join(directory, '*.tess')))
    random.seed(580)
    random.shuffle(files)
    samples = []
    for path in files:
        if len(samples) >= n:
            break
        with open(path, encoding='utf-8', errors='surrogateescape') as f:
            for line in f:
                line = line.rstrip('\r\n')
                tag, rest = split_tag(line)
                if PATTERN.search(rest):
                    samples.append((os.path.basename(path), tag, rest))
                    break  # one sample per file for variety
    return samples[:n]


def main():
    samples = find_sample_lines('texts/grc', 20)
    tp = TextProcessor()

    n_diff_tokens = 0
    n_diff_lemmas = 0
    report_lines = []
    for fname, tag, stored in samples:
        corrected = fix_line(stored)
        stored_result = tp.process_line(stored, language='grc')
        corrected_result = tp.process_line(corrected, language='grc')

        tokens_differ = stored_result['tokens'] != corrected_result['tokens']
        lemmas_differ = stored_result['lemmas'] != corrected_result['lemmas']
        if tokens_differ:
            n_diff_tokens += 1
        if lemmas_differ:
            n_diff_lemmas += 1

        report_lines.append({
            'file': fname,
            'tag': tag,
            'stored': stored,
            'corrected': corrected,
            'stored_tokens': stored_result['tokens'],
            'corrected_tokens': corrected_result['tokens'],
            'stored_lemmas': stored_result['lemmas'],
            'corrected_lemmas': corrected_result['lemmas'],
            'tokens_differ': tokens_differ,
            'lemmas_differ': lemmas_differ,
        })

    print(f"Sampled {len(samples)} lines from affected files")
    print(f"Lines where TOKENS differ (stored vs corrected): {n_diff_tokens}")
    print(f"Lines where LEMMAS differ (stored vs corrected): {n_diff_lemmas}")
    print()
    for r in report_lines:
        print(f"--- {r['file']} {r['tag']}")
        print(f"  stored:    {r['stored'][:80]}")
        print(f"  corrected: {r['corrected'][:80]}")
        print(f"  tokens_differ={r['tokens_differ']} lemmas_differ={r['lemmas_differ']}")
        if r['tokens_differ'] or r['lemmas_differ']:
            # show first differing token/lemma pair
            for i, (st, ct) in enumerate(zip(r['stored_tokens'], r['corrected_tokens'])):
                if st != ct:
                    print(f"    token[{i}]: stored={st!r} corrected={ct!r}")
            for i, (sl, cl) in enumerate(zip(r['stored_lemmas'], r['corrected_lemmas'])):
                if sl != cl:
                    print(f"    lemma[{i}]: stored={sl!r} corrected={cl!r}")


if __name__ == '__main__':
    main()
