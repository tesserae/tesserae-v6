#!/usr/bin/env python3
"""Judge whether each scholarship article bears on the event it is listed under.

  judge_scholarship_relevance.py INPUT.sqlite OUTPUT.sqlite [--limit N] [--events Q844289,...]

For every distinct (event, article) pair in the `scholarship` table (kind 'article')
the gateway model reads the event (label, dates, place, participants, description)
and what the citation indexes hold about the article (title, authors, journal, year,
and the sentences in which the article cites the event's passages) and answers
YES, PARTLY or NO with a reason of at most fifteen words. The citation indexes keep
no abstracts, so the prompt says "no abstract held" and gives the citing sentences
in its place. OUTPUT is a copy of INPUT with the table `scholarship_relevance`
added and nothing else changed. A run that stops can be started again: pairs
already in OUTPUT are skipped. Run from the repository root.

The gateway address and key come from ~/.config/tesserae/bullsai.env. At most 8
requests are in flight. A 429 is retried after 30 seconds. A 402 or a quota
message stops the run, with everything judged so far saved.
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MODEL = 'zai-org/GLM-5.3-Flash'
ENV_FILE = os.path.expanduser('~/.config/tesserae/bullsai.env')
DEFAULT_URL = 'https://gateway.bullsai.buffalo.edu'
EXTRA_FIELDS = {'chat_template_kwargs': {'enable_thinking': False}}
MAX_IN_FLIGHT = 8
MAX_TOKENS = 1200
RETRY_MAX_TOKENS = 3500  # a reply that ran out before its verdict line is asked again with more room
RETRY_429_SECONDS = 30
INDEX_DIR = '/var/www/tesseraev6_flask/data/citation_index'
MAX_SENTENCES = 4
SENTENCE_CHARS = 450

SYSTEM = ('You are a classical scholar deciding whether a journal article bears on a historical event. '
          'Answer on one line: YES, PARTLY or NO, a tab, then the reason in at most fifteen words. '
          'YES means the article discusses the event, its participants, its place at the time, or the ancient account of it. '
          'PARTLY means it treats the passage or the work in a way that touches the event. '
          'NO means it cites the passage for something else, such as grammar, textual criticism of a word, or a different subject. '
          'Think as briefly as you can. Example reply: NO<tab>Cites Thucydides 7.50 only to illustrate a Greek word.')


class QuotaStop(Exception):
    pass


def _env():
    vals = {}
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                vals[k.strip()] = v.strip().strip('"\'')
    url = (os.environ.get('BULLSAI_URL') or vals.get('BULLSAI_URL') or DEFAULT_URL).rstrip('/')
    key = os.environ.get('BULLSAI_API_KEY') or vals.get('BULLSAI_API_KEY') or ''
    if not key:
        sys.exit('no BULLSAI_API_KEY in the environment or ' + ENV_FILE)
    return url, key


def _year(n):
    if n is None:
        return '?'
    return f'{-n} BCE' if n < 0 else f'{n} CE'


def event_text(e):
    parts = [f'Event: {e["label"]}']
    if e['date_start'] is not None:
        d = _year(e['date_start'])
        if e['date_end'] is not None and e['date_end'] != e['date_start']:
            d += ' to ' + _year(e['date_end'])
        parts.append('Dates: ' + d)
    if e['place']:
        parts.append('Place: ' + e['place'])
    if e['participants']:
        parts.append('Participants: ' + str(e['participants'])[:300])
    desc = ' '.join(x for x in (e['description'], e['summary']) if x)
    if desc:
        parts.append('Description: ' + desc[:700])
    return '\n'.join(parts)


def article_text(art, ev_refs):
    head = [f'Article: {art["title"]}']
    if art.get('authors'):
        head.append('Authors: ' + '; '.join(art['authors']))
    head.append('Venue: %s, %s' % (art.get('venue') or '?', art.get('year') or '?'))
    head.append('Abstract: no abstract held')
    head.append('Passages of the event it cites: ' + '; '.join(sorted(ev_refs)))
    sents = art.get('snippets') or []
    if sents:
        head.append('Sentences in which it cites them:')
        for cite, s in sents[:MAX_SENTENCES]:
            head.append(f'- ({cite}) {s[:SENTENCE_CHARS]}')
    return '\n'.join(head)


FORMAT_TAIL = '\n\nReply with exactly one line in the form VERDICT<tab>reason, where VERDICT is YES, PARTLY or NO.'


def parse(text):
    """The verdict line. With thinking off the model often talks its way to the answer and ends
    on the line asked for (VERDICT, a tab, the reason), so the last such line is the answer."""
    t = (text or '').strip()
    found = re.findall(r'(YES|PARTLY|NO)[ ]*(?:\t|<tab>)[ ]*([^\n]+)', t)
    if not found:
        found = re.findall(r'(?m)^\W*(YES|PARTLY|NO)\b[ ]*[:\-\u2014]+[ ]*([^\n]+)$', t)
    if not found:
        return None, t[-200:]
    v, reason = found[-1]
    reason = re.split(r'(?:YES|PARTLY|NO)[ ]*(?:\t|<tab>)', reason)[0]
    return v, re.sub(r'\s+', ' ', reason).strip()[:240]


def ask(url, key, user, stats, lock, max_tokens=MAX_TOKENS):
    body = json.dumps({'model': MODEL, 'temperature': 0, 'max_tokens': max_tokens,
                       'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}],
                       **EXTRA_FIELDS}).encode()
    req = urllib.request.Request(url + '/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    for attempt in range(6):
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read())
            u = d.get('usage') or {}
            with lock:
                stats['requests'] += 1
                stats['seconds'] += time.time() - t0
                stats['prompt_tokens'] += u.get('prompt_tokens', 0)
                stats['completion_tokens'] += u.get('completion_tokens', 0)
            return d['choices'][0]['message']['content'] or ''
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode('utf-8', 'replace')
            if e.code == 429:
                with lock:
                    stats['n429'] += 1
                time.sleep(RETRY_429_SECONDS)
                continue
            if e.code == 402 or 'quota' in msg.lower():
                with lock:
                    stats['n402'] += 1
                raise QuotaStop(f'HTTP {e.code}: {msg}')
            with lock:
                stats['errors'] += 1
            time.sleep(5)
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError):
            with lock:
                stats['errors'] += 1
            time.sleep(5)
    return None


def gather(c, only_events, limit):
    """{(event_id, url, title): {'refs': set, 'art': dict}} with the citing sentences."""
    from backend import scholarship as S
    from relink_scholarship import span_of, passage_ref
    S.CITATION_INDEX = os.path.join(INDEX_DIR, 'citations.db')
    extra = os.path.join(INDEX_DIR, 'citations_muse.db')
    if os.path.exists(extra):
        os.environ[S.CITATIONS_EXTRA_ENV] = extra
    c.row_factory = sqlite3.Row
    events = {r['id']: r for r in c.execute('SELECT * FROM events')}
    rows = c.execute("SELECT * FROM scholarship WHERE kind = 'article' ORDER BY event_id, rowid").fetchall()
    by_event = {}
    for r in rows:
        if only_events and r['event_id'] not in only_events:
            continue
        by_event.setdefault(r['event_id'], []).append(r)
    cache = {}

    def hits(work, lo, hi):
        key = (work, lo, hi)
        if key not in cache:
            try:
                res = S.citation_index(S.passage_names(work, lo, hi), limit=100000).get('results', [])
            except Exception as e:
                print(f'  lookup failed {work} {lo}: {type(e).__name__}: {e}', file=sys.stderr)
                res = []
            cache[key] = {(x.get('url'), x.get('title')): x for x in res}
        return cache[key]

    out = {}
    for eid, srows in by_event.items():
        plist = [dict(r) for r in c.execute(
            'SELECT rank, work, ref_start, ref_end FROM passages WHERE event_id = ? '
            "AND (rank <= 10 OR llm_label = 'yes') ORDER BY rank", (eid,))]
        by_ref = {}
        for p in plist:
            by_ref.setdefault(passage_ref(p), []).append((p['work'], p['ref_start'], p['ref_end']))
        for work, lo, hi in span_of(plist):
            by_ref.setdefault(passage_ref({'ref_start': lo, 'ref_end': hi}), []).append((work, lo, hi))
        for r in srows:
            key = (eid, r['url'], r['title'])
            ent = out.setdefault(key, {'refs': set(), 'art': {'title': r['title'], 'snippets': []}})
            ent['refs'].add(r['passage_ref'] or '?')
            for work, lo, hi in by_ref.get(r['passage_ref'], []):
                h = hits(work, lo, hi).get((r['url'], r['title']))
                if not h:
                    continue
                a = ent['art']
                a.setdefault('authors', h.get('authors'))
                a.setdefault('venue', h.get('venue'))
                a.setdefault('year', h.get('year'))
                if h.get('snippet') and all(s != h['snippet'] for _, s in a['snippets']):
                    a['snippets'].append((h.get('cites') or r['passage_ref'], h['snippet']))
    keys = sorted(out)
    if limit:
        keys = keys[:limit]
    return events, [(k, out[k]) for k in keys]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--events', default='')
    ap.add_argument('--max-seconds', type=int, default=0, help='stop cleanly after this long, run again to resume')
    a = ap.parse_args(argv)
    only = {x.strip() for x in a.events.split(',') if x.strip()}
    url, key = _env()
    if not os.path.exists(a.output):
        shutil.copyfile(a.input, a.output)
    c = sqlite3.connect(a.output)
    c.execute('CREATE TABLE IF NOT EXISTS scholarship_relevance (event_id TEXT, url TEXT, title TEXT, verdict TEXT, '
              'reason TEXT, model TEXT, judged_at TEXT, PRIMARY KEY (event_id, url, title))')
    c.commit()
    events, pairs = gather(c, only, a.limit)
    done = {(r[0], r[1], r[2]) for r in c.execute('SELECT event_id, url, title FROM scholarship_relevance')}
    todo = [(k, v) for k, v in pairs if k not in done]
    print(f'{len(pairs)} pairs, {len(done & {k for k, _ in pairs})} already judged, {len(todo)} to judge', flush=True)
    stats = {'requests': 0, 'seconds': 0.0, 'prompt_tokens': 0, 'completion_tokens': 0, 'n429': 0, 'n402': 0, 'errors': 0}
    lock = threading.Lock()
    t_start = time.time()
    n_ok = n_bad = 0
    stop = None

    def work(item):
        (eid, u, title), v = item
        user = event_text(events[eid]) + '\n\n' + article_text(v['art'], v['refs']) + FORMAT_TAIL
        text = ask(url, key, user, stats, lock)
        if text is not None and parse(text)[0] is None:
            text = ask(url, key, user, stats, lock, RETRY_MAX_TOKENS)
        return item, text

    it = iter(todo)
    with ThreadPoolExecutor(MAX_IN_FLIGHT) as ex:
        pending = set()
        exhausted = False
        while pending or not exhausted:
            if a.max_seconds and time.time() - t_start > a.max_seconds:
                exhausted = True
            while not exhausted and not stop and len(pending) < MAX_IN_FLIGHT:
                nxt = next(it, None)
                if nxt is None:
                    exhausted = True
                    break
                pending.add(ex.submit(work, nxt))
            if not pending:
                break
            finished = next(as_completed(pending))
            pending.discard(finished)
            try:
                item, text = finished.result()
            except QuotaStop as e:
                stop = str(e)
                exhausted = True
                continue
            if text is None:
                n_bad += 1
                continue
            verdict, reason = parse(text)
            if verdict is None:
                n_bad += 1
                print('  unparsed:', repr(text[-300:]), file=sys.stderr)
                continue
            (eid, u, title), _ = item
            c.execute('INSERT OR REPLACE INTO scholarship_relevance VALUES (?,?,?,?,?,?,?)',
                      (eid, u, title, verdict, reason, MODEL, time.strftime('%Y-%m-%d %H:%M:%S')))
            n_ok += 1
            if n_ok % 100 == 0:
                c.commit()
                print(f'  {n_ok} judged, {time.time() - t_start:.0f} s', flush=True)
    c.commit()
    counts = dict(c.execute('SELECT verdict, COUNT(*) FROM scholarship_relevance GROUP BY verdict').fetchall())
    wall = time.time() - t_start
    print(f'judged {n_ok}, failed {n_bad}, wall {wall:.0f} s; verdicts in store {counts}')
    r = stats['requests'] or 1
    print(f'requests {stats["requests"]}, mean {stats["seconds"] / r:.2f} s each, tokens {stats["prompt_tokens"]} prompt '
          f'+ {stats["completion_tokens"]} completion, 429s {stats["n429"]}, 402s {stats["n402"]}, other errors {stats["errors"]}')
    if stop:
        print('STOPPED on quota:', stop)
        sys.exit(3)


if __name__ == '__main__':
    main()
