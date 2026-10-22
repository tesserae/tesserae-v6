#!/usr/bin/env python3
"""A stricter check of the Theme Search passages added to the events nobody read by hand.

  strict_theme_filter.py APPLIED_STORE LIVE_STORE KEEP_FILE OUT_DIR --theme-cache CACHE.sqlite
                         [--window-texts DB] [--texts DIR] [--sample 60] [--grades GRADES.json]

add_theme_passages.py (2026-10-21) added 1,583 passages, found_by 'theme search 2026-10-21', to the
events store APPLIED_STORE. Only the events read by hand (KEEP_FILE) were installed. A random sample
of the other additions read 17 right, 7 partly right and 11 wrong: the wrong ones share only a name
with the event (Damon and Phintias under Issus) or tell another event (Livy's Metaurus under Cannae).

This script takes the added rows of the other events, which the live store LIVE_STORE does not hold,
and keeps a row only if both checks pass.

1. Evidence in the text. The passage's own lines must name the event's place (ancient or modern name),
   one of its participants, or a distinctive word of its name (Thermopylae, Cannae). The forms of a
   name come from the passages the event already had before the additions (their names_matched, read
   with events.name_excerpts, the code that highlights names on the events page), and from the stems
   of the words of place, place_ancient, the label and the participants, capitalized in Latin letters.
2. A strict second reading by the free campus gateway model: does the passage narrate THIS event?
   Answer YES, MENTION or NO with a quote of the line that shows it. A row is kept on YES or MENTION
   only when the quoted words are in the passage.

Then it draws a random sample of kept rows for reading (strict_sample_N.md) and writes a candidate
store, a copy of LIVE_STORE with the kept rows added. Nothing under /var/www is written. Answers are
cached, so a rerun costs nothing. At most 6 requests are in flight.
"""
import argparse
import hashlib
import json
import os
import random
import re
import sqlite3
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_scholarship_relevance as J  # noqa: E402
from add_theme_passages import EXTRA_FIELDS, FOUND_BY, MODEL, header, quote_in  # noqa: E402

MAX_IN_FLIGHT = 6
PROMPT_VERSION = 'strict v1, 2026-10-22'
TOKEN = re.compile(r'(?:[^\W\d_]|[̀-ͯ])+')
# Words that name a kind of event or a large power, not the place or people of this one.
GENERIC = {
    'battle', 'siege', 'sack', 'war', 'wars', 'treaty', 'peace', 'conquest', 'capture', 'fall', 'revolt', 'rebellion',
    'campaign', 'expedition', 'invasion', 'massacre', 'assassination', 'death', 'trial', 'naval', 'first', 'second',
    'third', 'fourth', 'fifth', 'great', 'the', 'and', 'of', 'in', 'at', 'on', 'for', 'ancient', 'rome', 'roman',
    'romans', 'republic', 'empire', 'kingdom', 'city', 'state', 'states', 'greece', 'greek', 'greeks', 'army',
    'forces', 'people', 'tribe', 'tribes', 'league', 'coalition', 'allied', 'allies', 'north', 'south', 'east',
    'west', 'upper', 'lower', 'new', 'old', 'mount', 'river', 'lake', 'bay', 'gulf', 'strait', 'pass', 'plain',
    'fields', 'near', 'from', 'with', 'during', 'after', 'before', 'under', 'over',
}
SYSTEM = (
    "You are a historian of the ancient world who reads Greek and Latin. You are given one historical EVENT "
    "(a battle, siege, treaty or similar, with its date, place, participants and a summary) and one PASSAGE of "
    "an ancient or later text. Decide, strictly, whether the passage is about THIS event.\n"
    "YES: the passage narrates or directly describes this event, its course or its immediate outcome.\n"
    "MENTION: the passage refers to this particular event, by name or by unmistakable allusion, but is about "
    "something else.\n"
    "NO: anything else. This includes an earlier or later event of the same kind at the same place or with the "
    "same people, a different person or place that shares a name with one in the event, a general account of "
    "the war or the period that does not reach this event, a passage that only resembles the event, and a "
    "passage whose lines you cannot connect to this event.\n"
    "Judge only what the passage shows. Reply with a short reason, then two last lines exactly of the form\n"
    "ANSWER: YES or ANSWER: MENTION or ANSWER: NO\n"
    "QUOTE: the words of the passage, in its own language and at most twelve words, that show it, or nothing for NO.")


def fold(E, s):
    return E._fold(s)


def words_of(text):
    return TOKEN.findall(unicodedata.normalize('NFC', str(text or '')))


def significant(phrase):
    """The distinctive words of a place, label or participant name."""
    out = []
    for w in words_of(phrase):
        if len(w) >= 4 and w.lower() not in GENERIC:
            out.append(w)
    return out


def stems_for(E, ev):
    """[(label, folded stem, max token length, needs capital)] for the event's place, name and participants."""
    seen, out = set(), []
    sources = [('place', ev.get('place_ancient')), ('place', ev.get('place')), ('name', ev['label'])]
    sources += [('participant', p) for p in ev['participants']]
    for kind, phrase in sources:
        for w in significant(phrase):
            f = fold(E, w)
            stem = f if len(f) < 6 else f[:-2]
            if stem in seen:
                continue
            seen.add(stem)
            latin = bool(re.match(r'[A-Za-z]', w))
            out.append(('%s [%s]' % (w, kind), stem, len(w) + 5, latin))
    return out


def evidence(E, ev, known_names, lines):
    """The names of the event found in the passage's lines. Empty when none."""
    found = []
    ex = E.name_excerpts(None, None, None, known_names, lines=lines) if known_names else []
    for e in ex:
        found += e['names']
    stems = stems_for(E, ev)
    for ln in lines:
        text = unicodedata.normalize('NFC', str(ln.get('text') or ''))
        for m in TOKEN.finditer(text):
            w = m.group(0)
            f = fold(E, w)
            for label, stem, longest, latin in stems:
                if latin and not w[:1].isupper():
                    continue
                if f.startswith(stem) and len(w) <= longest:
                    found.append(label)
    return sorted(set(found))


def read_keep(path):
    keep = set()
    for line in open(path, encoding='utf-8'):
        if line.startswith('KEEP '):
            keep |= set(line.split()[1:])
    return keep


def ask(url, key, ev, lines, ref, lang):
    text = '\n'.join('%s: %s' % (ln['ref'], str(ln['text'])[:600]) for ln in lines)
    user = header(ev) + '\nPASSAGE [%s, %s]\n%s' % (ref, lang, text)
    body = json.dumps({'model': MODEL, 'temperature': 0, 'max_tokens': 1200,
                       'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}],
                       **EXTRA_FIELDS}).encode()
    req = urllib.request.Request(url + '/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    if not req.full_url.startswith(('http://', 'https://')):
        raise ValueError('gateway URL must be http or https')
    for _ in range(5):
        try:
            with urllib.request.urlopen(req, timeout=240) as r:  # nosec B310 - scheme checked above
                reply = json.loads(r.read())['choices'][0]['message']['content'] or ''
            break
        except urllib.error.HTTPError as e:
            if e.code == 402:
                raise J.QuotaStop('HTTP 402')
            time.sleep(J.RETRY_429_SECONDS if e.code == 429 else 5)
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, KeyError):
            time.sleep(5)
    else:
        return None, '', ''
    m = re.search(r'ANSWER:\s*(YES|MENTION|NO)', reply, re.I)
    q = re.search(r'QUOTE:\s*(.*)', reply)
    quote = (q.group(1).strip().strip('"\'«»“”*') if q else '')[:200]
    return (m.group(1).upper() if m else None), quote, reply[:600]


def render_sample(path, sample, grades, summary):
    out = ['# Strict check: sample of %d kept passages (2026-10-22)\n' % len(sample), summary + '\n']
    for i, s in enumerate(sample, 1):
        g = grades.get(str(i)) or {}
        out.append('## %d. %s (%s) / %s\n' % (i, s['event_label'], s['event_id'], s['ref']))
        out.append('Event: %s, %s, at %s. Participants: %s.' % (s['event_label'], s['when'], s['place'], s['participants']))
        out.append('Model: %s. Quote: %s' % (s['verdict'], s['quote']))
        out.append('Names found in the text: %s\n' % ', '.join(s['evidence']))
        out.append('> ' + s['first300'].replace('\n', ' ') + '\n')
        out.append('Grade: %s. %s\n' % (g.get('grade', '(not yet graded)'), g.get('reason', '')))
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('applied')
    ap.add_argument('live')
    ap.add_argument('keep')
    ap.add_argument('out_dir')
    ap.add_argument('--theme-cache', required=True, help='theme_cache.sqlite of add_theme_passages (for event notes)')
    ap.add_argument('--window-texts')
    ap.add_argument('--texts')
    ap.add_argument('--sample', type=int, default=60)
    ap.add_argument('--grades', help='JSON {"1": {"grade": "right", "reason": "..."}} to print in the sample file')
    ap.add_argument('--limit', type=int, default=0, help='only the first N rows (a trial)')
    a = ap.parse_args(argv)
    for p in (a.out_dir,):
        if os.path.realpath(p).startswith('/var/www'):
            sys.exit('refusing to write under /var/www')
    os.makedirs(a.out_dir, exist_ok=True)
    if a.window_texts:
        os.environ['TESSERAE_WINDOW_TEXTS'] = a.window_texts
    from backend.blueprints import events as E
    if a.texts:
        E.TEXTS_ROOT = a.texts

    keep = read_keep(a.keep)
    src = sqlite3.connect('file:%s?mode=ro' % a.applied, uri=True)
    src.row_factory = sqlite3.Row
    live = sqlite3.connect('file:%s?mode=ro' % a.live, uri=True)
    in_live = set(live.execute('SELECT event_id, work, ref_start FROM passages WHERE found_by = ?', (FOUND_BY,)))
    events = {}
    for r in src.execute('SELECT * FROM events'):
        events[r['id']] = {'id': r['id'], 'label': r['label'], 'ds': r['date_start'], 'de': r['date_end'],
                           'place': r['place'], 'place_ancient': r['place_ancient'],
                           'participants': json.loads(r['participants'] or '[]'),
                           'description': r['description'], 'summary': r['summary']}
    notes = dict(sqlite3.connect('file:%s?mode=ro' % a.theme_cache, uri=True).execute('SELECT event, note FROM notes'))
    for ev in events.values():
        if not (ev['summary'] or '').strip():
            ev['summary'] = notes.get(ev['id']) or ''

    # Name forms from the passages the event had before the additions (names_matched), without the
    # context names (a war or a work the passage belongs to) and without those set aside.
    known = {}
    for r in src.execute("SELECT event_id, names_matched FROM passages WHERE COALESCE(found_by, '') <> ?", (FOUND_BY,)):
        for n in json.loads(r['names_matched'] or '[]'):
            if ' = ' in str(n) and '[context]' not in str(n):
                known.setdefault(r['event_id'], {}).setdefault(str(n).rsplit(' = ', 1)[0], set()).update(
                    f.strip() for f in str(n).rsplit(' = ', 1)[1].split(',') if f.strip())

    rows = [r for r in src.execute('SELECT rowid AS rid, * FROM passages WHERE found_by = ? ORDER BY event_id, rank',
                                   (FOUND_BY,))
            if r['event_id'] not in keep and (r['event_id'], r['work'], r['ref_start']) not in in_live]
    if a.limit:
        rows = rows[:a.limit]
    counts = {'rows considered': len(rows), 'events considered': len({r['event_id'] for r in rows})}

    # Step 1.
    step1, lost = [], 0
    for r in rows:
        ev = events[r['event_id']]
        lines = E._passage_lines(r['work'], r['language'], r['ref_start'], r['ref_end'])
        if not lines:
            lost += 1
            continue
        names = ['%s = %s' % (h, ', '.join(sorted(fs))) for h, fs in known.get(r['event_id'], {}).items()]
        ev_names = evidence(E, ev, names, lines)
        if ev_names:
            step1.append((r, lines, ev_names))
    counts['rows with no text found'] = lost
    counts['passing step 1 (evidence in the text)'] = len(step1)
    counts['events passing step 1'] = len({r['event_id'] for r, _l, _n in step1})
    print(counts, flush=True)

    # Step 2.
    url, key = J._env()
    cache = sqlite3.connect(os.path.join(a.out_dir, 'strict_cache.sqlite'), check_same_thread=False)
    cache.execute('CREATE TABLE IF NOT EXISTS answers (event TEXT, window_id TEXT, prompt TEXT, verdict TEXT, quote TEXT, '
                  'reply TEXT, model TEXT, ts TEXT, PRIMARY KEY (event, window_id, prompt))')
    lock = threading.Lock()
    done = {}
    for e, w, v, q in cache.execute('SELECT event, window_id, verdict, quote FROM answers WHERE prompt = ? AND verdict IS NOT NULL',
                                    (PROMPT_VERSION,)):
        done[(e, w)] = (v, q)

    def one(item):
        r, lines, _names = item
        k = (r['event_id'], r['window_id'])
        if k in done:
            return item, done[k]
        verdict, quote, reply = ask(url, key, events[r['event_id']], lines[:16], r['ref_start'], r['language'])
        with lock:
            cache.execute('INSERT OR REPLACE INTO answers VALUES (?,?,?,?,?,?,?,?)',
                          (r['event_id'], r['window_id'], PROMPT_VERSION, verdict, quote, reply, MODEL,
                           time.strftime('%Y-%m-%d %H:%M:%S')))
            cache.commit()
        return item, (verdict, quote)

    kept, answers = [], {'YES': 0, 'MENTION': 0, 'NO': 0, 'no answer': 0}
    quote_missing = 0
    with ThreadPoolExecutor(MAX_IN_FLIGHT) as pool:
        for (r, lines, names), (verdict, quote) in pool.map(one, step1):
            answers[verdict or 'no answer'] += 1
            if verdict in ('YES', 'MENTION'):
                if quote_in(quote, lines[:16]):
                    kept.append((r, lines, names, verdict, quote))
                else:
                    quote_missing += 1
    counts.update({'step 2 answers': answers, 'YES or MENTION whose quote is not in the passage': quote_missing,
                   'kept': len(kept), 'events gaining passages': len({k[0]['event_id'] for k in kept})})
    print(counts, flush=True)

    # Sample.
    # The rows with the smallest hash of seed and key, so one more or fewer kept row changes at most one pick.
    pick = sorted(kept, key=lambda k: hashlib.sha1(('22|%s|%s' % (k[0]['event_id'], k[0]['window_id'])).encode()).hexdigest())
    pick = sorted(pick[:a.sample], key=lambda k: k[0]['rid'])
    random.Random(22).shuffle(pick)
    sample = []
    for r, lines, names, verdict, quote in pick:
        ev = events[r['event_id']]
        first = ' '.join(str(ln['text']) for ln in lines)
        sample.append({'event_id': ev['id'], 'event_label': ev['label'], 'ref': r['ref_start'], 'verdict': verdict,
                       'quote': quote, 'evidence': names, 'first300': first[:300],
                       'when': '%s to %s' % (ev['ds'], ev['de']), 'place': ev['place_ancient'] or ev['place'] or '',
                       'participants': ', '.join(ev['participants'][:5])})
    grades = json.load(open(a.grades)) if a.grades else {}
    summary = 'Rows considered %d, passing step 1 %d, kept %d.' % (
        counts['rows considered'], counts['passing step 1 (evidence in the text)'], len(kept))
    render_sample(os.path.join(a.out_dir, 'strict_sample_%d.md' % a.sample), sample, grades, summary)
    with open(os.path.join(a.out_dir, 'strict_report.json'), 'w') as f:
        json.dump({'counts': counts, 'sample': sample,
                   'kept': [{'event': k[0]['event_id'], 'work': k[0]['work'], 'ref_start': k[0]['ref_start'],
                             'verdict': k[3], 'quote': k[4]} for k in kept]}, f, indent=1, ensure_ascii=False)

    # Candidate store: the live store with the kept rows added, as keep_theme_additions.py leaves them.
    out = os.path.join(a.out_dir, 'event_dossiers_strict.sqlite')
    if os.path.exists(out):
        os.remove(out)
    dst = sqlite3.connect(out)
    live.backup(dst)
    cols = [c[1] for c in dst.execute('PRAGMA table_info(passages)')]
    top = {}
    for r, _lines, _names, _v, _q in kept:
        eid = r['event_id']
        if eid not in top:
            top[eid] = dst.execute('SELECT MAX(CAST(rank AS INTEGER)) FROM passages WHERE event_id = ?', (eid,)).fetchone()[0] or 0
        top[eid] += 1
        row = {c: (r[c] if c in r.keys() else None) for c in cols}
        row['rank'] = str(top[eid])
        dst.execute('INSERT INTO passages (%s) VALUES (%s)' % (', '.join(cols), ', '.join('?' * len(cols))),
                    [row[c] for c in cols])
    dst.commit()
    check = dst.execute('PRAGMA integrity_check').fetchone()[0]
    n_theme = dst.execute('SELECT COUNT(*) FROM passages WHERE found_by = ?', (FOUND_BY,)).fetchone()[0]
    dst.close()
    sha = hashlib.sha256(open(out, 'rb').read()).hexdigest()
    with open(out + '.sha256', 'w') as f:
        f.write('%s  %s\n' % (sha, os.path.basename(out)))
    print(json.dumps({'candidate': out, 'integrity': check, 'theme rows in it': n_theme,
                      'sha256': sha}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
