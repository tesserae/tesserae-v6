#!/usr/bin/env python3
"""Write blobs.jsonl.gz ({id, text}) for the campus GPU encoder from a
descriptions file, using the same text the index build embeds
(apply_passage_rows.blob_for, which carries the 'query: ' prefix).

    python scripts/corpus/make_encode_blobs.py descriptions.jsonl blobs.jsonl.gz

Rows without a description (errors) are skipped. Prints the row count.
"""
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apply_passage_rows import blob_for  # noqa: E402


def main(src, dst):
    n = 0
    seen = set()
    with open(src, encoding='utf-8') as fh, gzip.open(dst, 'wt', encoding='utf-8') as out:
        for line in fh:
            r = json.loads(line)
            if 'desc' not in r or r['id'] in seen:
                continue
            seen.add(r['id'])
            out.write(json.dumps({'id': r['id'], 'text': blob_for(r['desc'])},
                                 ensure_ascii=False) + '\n')
            n += 1
    print(n)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
