#!/usr/bin/env python3
"""Build desc_vocab.json: the words that occur in the passage descriptions.

Theme Search uses the file to tell a reader which words of the query no passage
description contains (backend/passage_index.py, unknown_query_words). The words
are every lowercase alphabetic token ([a-z]+ over the lowercased text) of each
row's `blob` and of the string and list values in its `desc`, counted once per
row, and kept when at least --min-count rows hold them.

    python scripts/corpus/build_desc_vocab.py \
        --descriptions data/passage_index/descriptions.jsonl \
        --out data/passage_index/desc_vocab.json

One pass over the file; memory is the word counter (about 100,000 words).
Rebuild after every append to the passage index.
"""
import argparse
import datetime
import json
import os
import re
import sys
from collections import Counter

TOKEN = re.compile(r'[a-z]+')


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)


def row_words(row):
    """The set of words one description row holds."""
    words = set(TOKEN.findall((row.get('blob') or '').lower()))
    desc = row.get('desc')
    if isinstance(desc, dict):
        for text in _strings(desc):
            words.update(TOKEN.findall(text.lower()))
    return words


def build(descriptions, min_count=2):
    counts = Counter()
    rows = 0
    with open(descriptions, encoding='utf-8') as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            rows += 1
            counts.update(row_words(row))
    words = {w: c for w, c in counts.items() if c >= min_count}
    return {'built': datetime.datetime.now().isoformat(timespec='seconds'),
            'rows': rows, 'min_count': min_count, 'words': words}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--descriptions', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--min-count', type=int, default=2)
    args = ap.parse_args(argv)
    result = build(args.descriptions, args.min_count)
    tmp = args.out + '.tmp'
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(result, fh, ensure_ascii=True, separators=(',', ':'))
    os.replace(tmp, args.out)
    print(f"{result['rows']} rows, {len(result['words'])} words kept "
          f"(min count {result['min_count']}) -> {args.out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
