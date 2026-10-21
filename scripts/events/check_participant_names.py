#!/usr/bin/env python3
"""Ask whether each participant's name in an event passage refers to that participant, and set aside the ones that do not.

  check_participant_names.py INPUT.sqlite OUTPUT.sqlite --cache CACHE.sqlite
                             [--texts DIR] [--window-texts DB] [--event ID] [--report PATH] [--apply]

The project lead, 2026-10-21, on the Battle of Actium: "why does it say agrippa was found in
the first passage". The names of an event passage are matched by their forms alone, so
Suetonius's "Agrippam nepotem" (Agrippa Postumus, Augustus 19.2) and Tacitus's "Haterium
Agrippam" (Annals 2.51) were listed as Marcus Agrippa. For every "[participant]" name in a
passage not judged unrelated, the line that holds the name is found and the free BullsAI
gateway model (the access rules and key file of judge_scholarship_relevance.py) is asked
whether the name there refers to the event's participant: YES, NO (a different person or
group who shares the name) or UNSURE, for up to three occurrences of each name. A name is
set aside only when every occurrence checked is NO. It moves from
names_matched to a new column names_set_aside, as {"name", "ref", "reason"}. Answers are
cached by event, name and line, so a rerun costs nothing. INPUT is never modified. Dry
run (cache filled, report written, no store) unless --apply. OUTPUT may not be under
/var/www. At most 8 requests are in flight. A 429 is retried after 30 seconds, a 402 or
quota message stops the run with the answers so far kept.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
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

SYSTEM = ('You are a classical scholar and prosopographer. You are given a historical event, one of its '
          'participants (a person, a people or a state) and one line of an ancient text that contains a word '
          'matched to that participant\'s name. Decide whether the word in this line refers to that same '
          'participant. Answer NO only when the line itself shows that it is a different person or group who '
          'shares the name: a relative or descendant (a son, grandson or nephew of the same name), a namesake '
          'with a different family name or title, or a person of another period. Answer UNSURE when the line '
          'does not settle it. Otherwise answer YES. Think in at most two short sentences, then end with a last '
          'line of the form ANSWER: YES, ANSWER: NO or ANSWER: UNSURE, followed on the same line by a dash and '
          'a reason of at most twelve words.')


def year_text(y):
    return '%d %s' % (abs(y), 'BCE' if y < 0 else 'CE')


def question(event, ds, de, participant, form, ref, line):
    when = year_text(ds) if ds == de else '%s to %s' % (year_text(ds), year_text(de))
    return ('Event: %s (%s)\nParticipant: %s\nWord matched to the participant: %s\nLine (%s): %s'
            % (event, when, participant, form, ref, line))


def parse(text):
    """('YES' | 'NO' | 'UNSURE' | None, reason)."""
    t = text or ''
    k = t.rfind('ANSWER:')
    if k < 0:
        return None, ''
    rest = t[k + 7:].strip().splitlines()[0] if t[k + 7:].strip() else ''
    word = rest.split()[0].strip('*.,:;-') .upper() if rest.split() else ''
    reason = rest.split('-', 1)[1].strip() if '-' in rest else ''
    return (word if word in ('YES', 'NO', 'UNSURE') else None), reason[:160]


def ask(url, key, user, stats, lock, max_tokens=400):
    body = json.dumps({'model': J.MODEL, 'temperature': 0, 'max_tokens': max_tokens,
                       'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}],
                       **J.EXTRA_FIELDS}).encode()
    req = urllib.request.Request(url + '/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    if not req.full_url.startswith(('http://', 'https://')):
        raise ValueError('gateway URL must be http or https')
    for _ in range(6):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:  # nosec B310 - scheme checked above
                d = json.loads(r.read())
            with lock:
                stats['requests'] += 1
            return (d['choices'][0]['message']['content'] or '').strip()
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode('utf-8', 'replace')
            if e.code == 429:
                with lock:
                    stats['n429'] += 1
                time.sleep(J.RETRY_429_SECONDS)
                continue
            if e.code == 402 or 'quota' in msg.lower():
                raise J.QuotaStop('HTTP %s: %s' % (e.code, msg))
            with lock:
                stats['errors'] += 1
            time.sleep(5)
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError):
            with lock:
                stats['errors'] += 1
            time.sleep(5)
    return None


def jobs_for(con, events, lines_of):
    """One job per occurrence, up to three, of each participant name in a passage."""
    from backend.blueprints import events as E
    out = []
    q = ("SELECT p.rowid, p.event_id, p.work, p.ref_start, p.ref_end, p.names_matched, p.language, "
         "e.label, e.date_start, e.date_end FROM passages p JOIN events e ON e.id = p.event_id "
         "WHERE COALESCE(p.llm_label, '') <> 'no'")
    for rowid, eid, work, rs, re_, nm, lang, label, ds, de in con.execute(q):
        if events and eid not in events:
            continue
        try:
            names = json.loads(nm or '[]')
        except ValueError:
            continue
        mine = [n for n in names if '[participant]' in str(n) and ' = ' in str(n)]
        if not mine or ds is None:
            continue
        lines = lines_of(work, lang, rs, re_)
        if not lines:
            continue
        for n in mine:
            lab = str(n).rsplit(' = ', 1)[0].split(' [')[0].strip()
            forms = {E._fold(f.strip()) for f in str(n).rsplit(' = ', 1)[1].split(',') if f.strip()}
            seen = 0
            for ln in lines:
                text = unicodedata.normalize('NFC', str(ln.get('text') or ''))
                if any(E._fold(m.group(0)) in forms
                       for m in re.finditer(r'(?:[^\W\d_]|[\u0300-\u036f])+', text)):
                    out.append({'rowid': rowid, 'event': eid, 'label': label,
                                'ds': min(ds, de if de is not None else ds), 'de': max(ds, de if de is not None else ds),
                                'name': n, 'participant': lab, 'form': str(n).rsplit(' = ', 1)[1],
                                'ref': ln.get('ref'), 'line': text[:900]})
                    seen += 1
                    if seen >= 3:
                        break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--cache', required=True)
    ap.add_argument('--texts', help='corpus texts folder (default: the repository texts/)')
    ap.add_argument('--window-texts', help='window_texts.db (default: the repository copy)')
    ap.add_argument('--event', action='append', default=[])
    ap.add_argument('--report')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    if os.path.realpath(a.output).startswith('/var/www'):
        sys.exit('refusing to write under /var/www')
    if a.texts:
        os.environ['TESSERAE_TEXTS_DIR'] = a.texts
    if a.window_texts:
        os.environ['TESSERAE_WINDOW_TEXTS'] = a.window_texts
    from backend.blueprints import events as E
    if a.texts:
        E.TEXTS_ROOT = a.texts
    src = sqlite3.connect('file:%s?mode=ro' % a.input, uri=True)
    jobs = jobs_for(src, set(a.event), E._passage_lines)
    for j in jobs:
        j['q'] = question(j['label'], j['ds'], j['de'], j['participant'], j['form'], j['ref'], j['line'])
        j['sha'] = hashlib.sha1((J.MODEL + SYSTEM + j['q']).encode()).hexdigest()[:16]
    cache = sqlite3.connect(a.cache)
    cache.execute('CREATE TABLE IF NOT EXISTS answers (sha TEXT PRIMARY KEY, question TEXT, answer TEXT, '
                  'model TEXT, ts TEXT)')
    have = {r[0]: r[1] for r in cache.execute('SELECT sha, answer FROM answers')}
    # An answer cut off before its ANSWER line is asked again with room to finish.
    todo = [j for j in jobs if j['sha'] not in have or parse(have[j['sha']])[0] is None]
    retry = {j['sha'] for j in todo if j['sha'] in have}
    stats = {'requests': 0, 'n429': 0, 'errors': 0}
    print('name occurrences %d, to ask %d (%d again, cut off before)' % (len(jobs), len(todo), len(retry)), flush=True)
    if todo:
        url, key = J._env()
        lock, stop = threading.Lock(), []

        def work(j):
            if stop:
                return None
            try:
                return j, ask(url, key, j['q'], stats, lock, 1500 if j['sha'] in retry else 400)
            except J.QuotaStop as e:
                stop.append(str(e))
                return None

        with ThreadPoolExecutor(J.MAX_IN_FLIGHT) as ex:
            for n, res in enumerate(ex.map(work, todo)):
                if res and res[1] is not None:
                    j, text = res
                    cache.execute('INSERT OR REPLACE INTO answers VALUES (?,?,?,?,?)',
                                  (j['sha'], j['q'], text, J.MODEL, time.strftime('%Y-%m-%d %H:%M:%S')))
                    if n % 50 == 0:
                        cache.commit()
                        print('  %d of %d' % (n + 1, len(todo)), flush=True)
        cache.commit()
        if stop:
            print('stopped: ' + stop[0], file=sys.stderr)
            return 3
    answers = {r[0]: r[1] for r in cache.execute('SELECT sha, answer FROM answers')}
    rep = {'occurrences': len(jobs), 'YES': 0, 'NO': 0, 'UNSURE': 0, 'unparsed': 0, 'gateway': stats}
    detail, by_name = [], {}
    for j in jobs:
        verdict, reason = parse(answers.get(j['sha']))
        rep[verdict or 'unparsed'] += 1
        detail.append({'event': j['event'], 'label': j['label'], 'name': j['name'], 'ref': j['ref'],
                       'line': j['line'][:300], 'verdict': verdict, 'reason': reason})
        by_name.setdefault((j['rowid'], j['name']), []).append((verdict, j['ref'], reason))
    # A name is set aside only when every occurrence checked is a different person.
    aside = {}
    for (rowid, name), vs in by_name.items():
        if all(v == 'NO' for v, _, _ in vs):
            aside.setdefault(rowid, []).append({'name': name, 'ref': vs[0][1], 'reason': vs[0][2]})
    rep['names_set_aside'] = sum(len(v) for v in aside.values())
    rep['passages_changed'] = len(aside)
    if a.report:
        with open(a.report, 'w') as f:
            json.dump({'summary': rep, 'occurrences': detail}, f, indent=1, ensure_ascii=False)
    print(json.dumps(rep))
    if not a.apply:
        print('dry run, no store written')
        return 0
    shutil.copyfile(a.input, a.output)
    dst = sqlite3.connect(a.output)
    if 'names_set_aside' not in [r[1] for r in dst.execute('PRAGMA table_info(passages)')]:
        dst.execute('ALTER TABLE passages ADD COLUMN names_set_aside TEXT')
    for rowid, items in aside.items():
        nm = json.loads(dst.execute('SELECT names_matched FROM passages WHERE rowid = ?', (rowid,)).fetchone()[0] or '[]')
        gone = {i['name'] for i in items}
        dst.execute('UPDATE passages SET names_matched = ?, names_set_aside = ? WHERE rowid = ?',
                    (json.dumps([n for n in nm if n not in gone], ensure_ascii=False),
                     json.dumps(items, ensure_ascii=False), rowid))
    dst.commit()
    print('written', a.output, 'passages changed', len(aside))
    return 0


if __name__ == '__main__':
    sys.exit(main())
