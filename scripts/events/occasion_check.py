"""Events: drop Theme Search passages that tell the same people on another occasion (2026-10-22).

After strict_theme_filter.py, a sample of its kept passages was about two thirds right and one in ten
wrong, and the wrong ones were nearly all the same people or place at another moment: Livy's siege of
Casilinum of 214 under the siege of 216, Cicero's Parthian scare of 51 BCE under the invasion of 40, the
second battle of Bedriacum under the first. Each added passage of a candidate store is read once more by the
free gateway model with the event's year, asking which occasion the passage concerns. A passage the model
places on another occasion is removed from the candidate store; THIS and UNCLEAR stay.

    occasion_check.py CANDIDATE_STORE THEME_CACHE OUT_DIR [--workers 4]
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import judge_scholarship_relevance as J  # noqa: E402
from add_theme_passages import EXTRA_FIELDS, FOUND_BY, MODEL, year_text  # noqa: E402

SYSTEM = ('You are a historian of the ancient world. You get an ancient event (with its year, place and '
          'participants) and a passage. Say in one sentence which occasion the passage concerns and its year '
          'if known. Then decide: THIS if the passage tells of or refers to this very event; OTHER if it tells '
          'of the same people, place or war on another occasion (an earlier or later battle, siege, campaign or '
          'treaty, or the same commander elsewhere); UNCLEAR if the passage does not let you tell. '
          'End with a last line OCCASION: THIS, OCCASION: OTHER or OCCASION: UNCLEAR.')


def ask(url, key, ev, lines):
    text = '\n'.join('%s: %s' % (ln['ref'], str(ln['text'])[:600]) for ln in lines)[:4000]
    when = year_text(ev['ds']) + (('' if ev['de'] == ev['ds'] else ' to ' + year_text(ev['de'])) if ev['de'] is not None else '')
    user = (f"EVENT: {ev['label']}, {when}, at {ev.get('place_ancient') or ev['place'] or 'unknown place'}. "
            f"Participants: {', '.join(ev['participants'][:8]) or 'not listed'}.\n"
            f"Summary: {(ev['summary'] or ev['description'] or '')[:500]}\n\nPASSAGE\n{text}")
    body = json.dumps({'model': MODEL, 'temperature': 0, 'max_tokens': 400,
                       'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}],
                       **EXTRA_FIELDS}).encode()
    req = urllib.request.Request(url + '/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    if not req.full_url.startswith(('http://', 'https://')):
        raise ValueError('gateway URL must be http or https')
    for _ in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:  # nosec B310 - scheme checked above
                reply = json.loads(r.read())['choices'][0]['message']['content'] or ''
            m = re.search(r'OCCASION:\s*(THIS|OTHER|UNCLEAR)', reply, re.I)
            return (m.group(1).upper() if m else 'UNCLEAR'), reply.strip()[:400]
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, KeyError):
            time.sleep(5)
    return 'UNCLEAR', 'no answer'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('store')
    ap.add_argument('theme_cache')
    ap.add_argument('out_dir')
    ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    from backend.blueprints import events as E
    url, key = J._env()
    db = sqlite3.connect(a.store)
    db.row_factory = sqlite3.Row
    notes = dict(sqlite3.connect('file:%s?mode=ro' % a.theme_cache, uri=True).execute('SELECT event, note FROM notes'))
    events = {}
    for r in db.execute('SELECT * FROM events'):
        events[r['id']] = {'id': r['id'], 'label': r['label'], 'ds': r['date_start'], 'de': r['date_end'],
                           'place': r['place'], 'place_ancient': r['place_ancient'],
                           'participants': json.loads(r['participants'] or '[]'),
                           'description': r['description'], 'summary': r['summary'] or notes.get(r['id']) or ''}
    keep_file = os.path.join(HERE, 'theme_additions_keep_2026-10-21.txt')
    hand = set()
    for line in open(keep_file, encoding='utf-8'):
        if line.startswith('KEEP '):
            hand |= set(line.split()[1:])
    rows = [r for r in db.execute('SELECT rowid, * FROM passages WHERE found_by = ?', (FOUND_BY,))
            if r['event_id'] not in hand and r['event_id'] not in ('Q160387', 'Q960915')]

    def one(r):
        lines = E._passage_lines(r['work'], r['language'], r['ref_start'], r['ref_end']) or []
        verdict, why = ask(url, key, events[r['event_id']], lines)
        return r['rowid'], r['event_id'], events[r['event_id']]['label'], r['ref_start'], verdict, why

    with ThreadPoolExecutor(a.workers) as ex:
        out = list(ex.map(one, rows))
    other = [o for o in out if o[4] == 'OTHER']
    db.executemany('DELETE FROM passages WHERE rowid = ?', [(o[0],) for o in other])
    db.commit()
    counts = {'rows read': len(out), 'THIS': sum(o[4] == 'THIS' for o in out), 'OTHER (removed)': len(other),
              'UNCLEAR': sum(o[4] == 'UNCLEAR' for o in out),
              'theme rows left': db.execute('SELECT count(*) FROM passages WHERE found_by = ?', (FOUND_BY,)).fetchone()[0],
              'integrity': db.execute('pragma integrity_check').fetchone()[0]}
    json.dump({'counts': counts, 'rows': out}, open(os.path.join(a.out_dir, 'occasion_report.json'), 'w'),
              ensure_ascii=False, indent=1)
    print(json.dumps(counts))


if __name__ == '__main__':
    sys.exit(main())
