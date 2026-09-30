#!/usr/bin/env python3
"""Read a sample of the assistant's recorded exchanges.

The record (backend/assistant/record.py) keeps one JSON line per exchange under
logs/assistant/<date>.jsonl. This prints the week's counts, the guard and
background-check verdicts, and a sample of answers to read, so that failures
become graded items in tests/fixtures/assistant/graded_questions.json.

    python scripts/assistant_record_review.py --days 7 --sample 20
"""
import argparse
import collections
import datetime as dt
import glob
import json
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=os.environ.get('TESSERAE_ASSISTANT_RECORD') or os.path.join(ROOT, 'logs', 'assistant'))
    ap.add_argument('--days', type=int, default=7)
    ap.add_argument('--sample', type=int, default=20)
    ap.add_argument('--seed', type=int, default=None)
    a = ap.parse_args()
    since = (dt.date.today() - dt.timedelta(days=a.days)).isoformat()
    rows = []
    for path in sorted(glob.glob(os.path.join(a.dir, '*.jsonl'))):
        if os.path.basename(path)[:10] < since:
            continue
        for line in open(path, encoding='utf-8'):
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    print(f'{len(rows)} exchanges since {since}')
    print('by route:', dict(collections.Counter(r.get('kind') for r in rows)))
    unclean = [r for r in rows if r.get('guardrails') and not r['guardrails'].get('clean', True)]
    revised = [r for r in rows if (r.get('background') or {}).get('revised')]
    print(f'guards not clean: {len(unclean)}   background sentences revised: {len(revised)}')
    for r in revised[:10]:
        print('  revised:', '; '.join(x.get('claim', '') for x in r['background']['revised'])[:160])
    random.seed(a.seed)
    for r in random.sample(rows, min(a.sample, len(rows))):
        print('\n---', r.get('ts'), r.get('kind'))
        print('Q:', (r.get('question') or '')[:300])
        print('A:', (r.get('answer') or '')[:900])


if __name__ == '__main__':
    main()
