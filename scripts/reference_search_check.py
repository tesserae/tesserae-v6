#!/usr/bin/env python3
"""The reference search, run against a running site. Exit code says pass/fail.

`tests/search_reference_tests.md` has said since 2026-08 that a search for
"arma virum" must return Ovid, Quintilian and Seneca, and that a search
which drops them is broken. It was a list for a person to read. This is the
same list as a command, so a deploy can end with it instead of with good
intentions. `tests/test_search_reference.py` is the other half: it runs the
lookup machinery over a miniature index, which continuous integration can
do, and it cannot see the corpus at all.

Usage:
    python scripts/reference_search_check.py
    python scripts/reference_search_check.py --base-url http://localhost:5000

Exits 0 when every check passes, 1 otherwise, and prints what it found
either way.

THE RESULT CAP MATTERS. A lemma search deduplicates across a whole work and
its book files AFTER the cap is applied, so the same query answers 323 at a
cap of 500 and 367 at 1,000. The figures below are at 1,000, which is what
the document means; asking for fewer is not a smaller version of the same
answer.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

# (search type, the fewest results a healthy corpus returns, authors that must
# appear with at least this many lines each). The minimums sit below today's
# numbers on purpose: this catches a broken search, not corpus growth.
CHECKS = [
    ('lemma', 300, {'Vergil': 15, 'Ovid': 10, 'Livy': 25, 'Quintilian': 1, 'Seneca': 1}),
    ('exact', 15, {'Vergil': 3, 'Ovid': 1, 'Quintilian': 1, 'Seneca': 1}),
]
QUERY = 'arma virum'
MAX_RESULTS = 1000


def run(base_url, search_type):
    body = json.dumps({'query': QUERY, 'language': 'la',
                       'search_type': search_type, 'max_results': MAX_RESULTS}).encode()
    req = urllib.request.Request(f'{base_url.rstrip("/")}/api/line-search', data=body,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base-url', default='https://tesserae.caset.buffalo.edu',
                    help='the site to check (default: production)')
    args = ap.parse_args()

    failures = []
    for search_type, floor, required in CHECKS:
        try:
            data = run(args.base_url, search_type)
        except (urllib.error.URLError, TimeoutError) as exc:
            failures.append(f'{search_type}: the search did not answer ({exc})')
            continue
        results = data.get('results') or []
        by_author = {}
        for row in results:
            by_author[row.get('author', '?')] = by_author.get(row.get('author', '?'), 0) + 1
        print(f'{search_type}: {len(results)} results, {len(by_author)} authors')
        for author, minimum in sorted(required.items()):
            found = by_author.get(author, 0)
            mark = 'ok ' if found >= minimum else 'MISSING'
            print(f'    {author:<12} {found:>4}  (needs {minimum}) {mark}')
            if found < minimum:
                failures.append(f'{search_type}: {author} returned {found}, needs {minimum}')
        if len(results) < floor:
            failures.append(f'{search_type}: {len(results)} results, fewer than {floor}')
        if len(by_author) < 5:
            failures.append(f'{search_type}: only {len(by_author)} authors, the corpus spans many')

    if failures:
        print('\nFAILED:')
        for f in failures:
            print(f'  {f}')
        return 1
    print('\nEvery reference check passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
