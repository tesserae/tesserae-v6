#!/usr/bin/env python3
"""A graded accuracy check for Tessa, the assistant, run against a live site.

Modelled on `scripts/reference_search_check.py`: this asks a fixed set of
real questions and exits non-zero when the answers get the facts wrong.
`tests/fixtures/assistant/graded_questions.json` holds about forty items,
each a `guide` question (posted to `/api/assistant/guide`) or an `analyze`
item (posted to `/api/assistant/analyze` against one of the three saved
result sets in `tests/fixtures/assistant/`).

Each item is graded on:
  - must_contain: a list of alternative phrases, ANY ONE of which must appear
    in the answer (case-insensitive). This is the fact or refusal the answer
    has to get right.
  - must_not_contain: phrases that mark a wrong answer if present.
  - for `analyze` items, the route's own `guardrails.clean` must be true.
    That means the model added no citation, quotation, or number that was
    not in the computed facts it was given.

THIS CHECKS FACTS AND REFUSALS, NOT WORDING. The model is not deterministic
at temperature 0.2 on the guide route (the analyze route runs at temperature
0.0, but even there phrasing varies), so `must_contain` lists are written
generously, with many acceptable phrasings for the same fact. A failure here
means a fact was missed or a refusal did not hold, not that the model chose
different words than the ones we guessed.

Usage:
    python scripts/assistant_accuracy_check.py
    python scripts/assistant_accuracy_check.py --base http://localhost:5000
    python scripts/assistant_accuracy_check.py --only refusal_invented_citation
    python scripts/assistant_accuracy_check.py --save out.jsonl

Exits 0 when every item passes, 1 otherwise, and prints one PASS/FAIL line
per item plus a summary either way.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'tests', 'fixtures', 'assistant')
QUESTIONS_PATH = os.path.join(FIXTURES_DIR, 'graded_questions.json')
TIMEOUT = 90


def _post(base, path, body):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(f'{base.rstrip("/")}{path}', data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as fh:
        return json.load(fh)


def _load_fixture(name):
    path = os.path.join(FIXTURES_DIR, f'{name}.json')
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


# The model writes typographic quotes and apostrophes ("I can't..." becomes
# "I can’t..."). A fixture written with plain ASCII quotes must still match.
_QUOTE_MAP = str.maketrans({
    '’': "'", '‘': "'", '“': '"', '”': '"', '–': '-', '—': '-',
})


def _norm(text):
    return text.translate(_QUOTE_MAP).lower()


def _contains_any(haystack, needles):
    h = _norm(haystack)
    return any(_norm(n) in h for n in needles)


def _contains_none(haystack, needles):
    h = _norm(haystack)
    return [n for n in needles if _norm(n) in h]


def run_item(base, item):
    """Post the item to the right route and return (answer_text, raw_response, error)."""
    if item['mode'] == 'guide':
        try:
            resp = _post(base, '/api/assistant/guide', {'question': item['question']})
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return None, None, f'the assistant did not answer ({exc})'
        answer = resp.get('answer')
        if not answer:
            return None, resp, resp.get('error') or 'no answer field in response'
        return answer, resp, None

    if item['mode'] == 'analyze':
        fixture = _load_fixture(item['fixture'])
        body = {
            'results': fixture['results'],
            'source': fixture['source'],
            'target': fixture['target'],
            'question': item['question'],
        }
        try:
            resp = _post(base, '/api/assistant/analyze', body)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return None, None, f'the assistant did not answer ({exc})'
        answer = resp.get('answer')
        if not answer:
            return None, resp, resp.get('note') or resp.get('error') or 'no answer field in response'
        return answer, resp, None

    return None, None, f"unknown mode {item['mode']!r}"


def grade(item, answer, resp):
    """Return a list of failure reasons; empty means the item passed."""
    reasons = []
    must_contain = item.get('must_contain') or []
    if must_contain and not _contains_any(answer, must_contain):
        reasons.append('missing required fact/refusal (none of must_contain matched)')

    hit = _contains_none(answer, item.get('must_not_contain') or [])
    if hit:
        reasons.append(f'contains forbidden phrase(s): {", ".join(hit)}')

    if item['mode'] == 'analyze':
        guardrails = (resp or {}).get('guardrails') or {}
        # An item may accept the removal of a sentence about access: the
        # question invites one, the guard exists to remove it, and a reading
        # that is otherwise clean has done what it should.
        tolerated = set(item.get('tolerate_guardrails') or [])
        offending = {k for k, v in guardrails.items()
                     if k != 'clean' and v and k not in tolerated}
        if not guardrails.get('clean') and offending:
            reasons.append(f'guardrails.clean is not true: {guardrails}')

    return reasons


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default='https://tesserae.caset.buffalo.edu',
                    help='the site to check (default: production)')
    ap.add_argument('--only', default=None, help='run only the item with this id')
    ap.add_argument('--save', default=None,
                    help='write every question, answer, and verdict to this JSONL file')
    args = ap.parse_args()

    with open(QUESTIONS_PATH, encoding='utf-8') as fh:
        items = json.load(fh)
    if args.only:
        items = [i for i in items if i['id'] == args.only]
        if not items:
            print(f'no item with id {args.only!r}', file=sys.stderr)
            return 1

    save_fh = open(args.save, 'w', encoding='utf-8') if args.save else None
    n_pass = n_fail = 0
    failures = []

    try:
        for item in items:
            answer, resp, error = run_item(args.base, item)
            if error:
                n_fail += 1
                snippet = ''
                print(f"FAIL {item['id']}: {error}")
                failures.append((item['id'], error, snippet))
                record = {'id': item['id'], 'mode': item['mode'], 'question': item['question'],
                          'answer': answer, 'response': resp, 'passed': False, 'reasons': [error]}
            else:
                reasons = grade(item, answer, resp)
                snippet = answer[:120].replace('\n', ' ')
                if reasons:
                    n_fail += 1
                    reason_text = '; '.join(reasons)
                    print(f"FAIL {item['id']}: {reason_text}")
                    print(f"      {snippet}")
                    failures.append((item['id'], reason_text, snippet))
                else:
                    n_pass += 1
                    print(f"PASS {item['id']}: {snippet}")
                record = {'id': item['id'], 'mode': item['mode'], 'question': item['question'],
                          'answer': answer, 'response': resp, 'passed': not reasons,
                          'reasons': reasons}
            if save_fh:
                save_fh.write(json.dumps(record, ensure_ascii=False) + '\n')
    finally:
        if save_fh:
            save_fh.close()

    print(f'\n{n_pass} passed, {n_fail} failed, {len(items)} total')
    if failures:
        print('\nFailed items:')
        for item_id, reason, snippet in failures:
            print(f'  {item_id}: {reason}')
            if snippet:
                print(f'      {snippet}')
        return 1
    print('Every graded item passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
