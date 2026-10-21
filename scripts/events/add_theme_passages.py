#!/usr/bin/env python3
"""Add to each event the passages Theme Search finds for its description, judged by the original labeling instructions.

  add_theme_passages.py INPUT.sqlite OUTPUT.sqlite --cache CACHE.sqlite [--event ID ...] [--limit 30]
                        [--extra-query TEXT ...]
                        [--base URL] [--texts DIR] [--window-texts DB] [--report PATH] [--apply]

The project lead, 2026-10-21, chose the Battle of Actium as an example for a presentation. Its
passages were gathered on 2026-10-09 by names and a coarse score, and the accounts of the battle
itself (Plutarch, Antony 62 to 68, Velleius 2.85, Eutropius 7.7) were not among its 100
candidates, while a Theme Search for the battle puts them in its first 25. For each event this
script runs three Theme Searches on the live site (queries_for and scene_query), keeps
the results that share no line with a passage the event already has, and asks the free BullsAI
gateway model to label each with the instructions of scripts/events/llm_judge.py on the
feat/event-anchor branch (SYSTEM below, unchanged): yes (narrates this event), mention, or no.
The yes and mention passages are added as new rows after the existing ones, with found_by set
to 'theme search 2026-10-21'. Theme Search requests go one at a time. Judgments are cached by
event and window, so a rerun costs nothing. INPUT is never modified. Dry run unless --apply.
OUTPUT may not be under /var/www.
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
import ssl
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_scholarship_relevance as J  # noqa: E402

FOUND_BY = 'theme search 2026-10-21'
# Four passages a request: the model reasons before its JSON and ran out of room at eight.
BATCH = 4
PROMPT_VERSION = 'llm_judge v1 instructions, 2026-10-21'

# The instructions of llm_judge.py (feat/event-anchor, 2026-10-09), unchanged, so a passage added
# here is judged as the existing ones were.
SYSTEM = (
    "You are a historian of the ancient world who reads Greek and Latin. You are given one historical "
    "EVENT (a battle, siege or treaty) with its date, place, participants and a short encyclopedia "
    "summary, and then numbered PASSAGES from ancient texts, each with an index description and some of "
    "its lines in the original language (and an English translation when one exists). For each passage "
    "decide whether it is about THIS event.\n"
    "yes: the passage narrates or directly describes this event, including its course, its immediate "
    "preparation or its outcome as part of the same narrative.\n"
    "mention: the passage refers to this event by name or by unmistakable allusion, but is about something "
    "else.\n"
    "no: the passage is about something else, including other battles, the same people or places on "
    "other occasions, and passages that only share names or vocabulary with the event. A passage with the "
    "same participants in a different year is 'no'.\n"
    "Judge only what the passage shows. Reply with JSON only, a list with one object per passage: "
    '[{"n": 1, "label": "yes|mention|no"}, ...].'
)


def year_text(y):
    return '%d %s' % (abs(y), 'BCE' if y < 0 else 'CE') if y is not None else ''


def base_work(work):
    return re.sub(r'\.part\..*$', '', str(work or ''))


def queries_for(ev):
    """Two searches, merged. The encyclopedia description reads like a scene and finds the
    accounts of the battle (Plutarch, Antony 62 and 67 for Actium) along with other sea
    battles. The name, date, place and leading participants find the passages that name
    them. Either alone missed what the other found (2026-10-21)."""
    when = year_text(ev['ds']) if ev['ds'] == ev['de'] else '%s to %s' % (year_text(ev['ds']), year_text(ev['de']))
    desc = '. '.join((ev.get('summary') or ev.get('description') or '').split('. ')[:2])
    place = ev.get('place_ancient') or ev.get('place') or ''
    who = ', '.join(ev['participants'][:4])
    out = [('%s, %s. %s' % (ev['label'], when, desc)).strip(' .')[:500],
           ('%s, %s, at %s: %s' % (ev['label'], when, place, who)).strip(' ,:')[:400]]
    return [q for q in dict.fromkeys(out) if q]


SCENE_SYSTEM = ('You write one-sentence descriptions of scenes for a search index of ancient texts. Given a '
                'historical event, describe in one sentence of at most 35 words what happens in it, as a scene, '
                'with no proper names, no dates and no place names: say who fights or negotiates (a queen, a '
                'consul, a besieged city), how, and how it ends. End your reply with a last line of the form '
                'SCENE: <the sentence>.')


def scene_query(url, key, ev):
    """A nameless account of what happens. The index descriptions seldom repeat proper names,
    so "a queen's ships suddenly hoist sail and flee, and her lover follows" finds Plutarch,
    Antony 64 and 66 and Cassius Dio 50.32, which the named queries miss (2026-10-21)."""
    body = json.dumps({'model': J.MODEL, 'temperature': 0, 'max_tokens': 1200,
                       'messages': [{'role': 'system', 'content': SCENE_SYSTEM},
                                    {'role': 'user', 'content': header(ev)}], **J.EXTRA_FIELDS}).encode()
    req = urllib.request.Request(url + '/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    if not req.full_url.startswith(('http://', 'https://')):
        raise ValueError('gateway URL must be http or https')
    try:
        with urllib.request.urlopen(req, timeout=180) as r:  # nosec B310 - scheme checked above
            text = (json.loads(r.read())['choices'][0]['message']['content'] or '').strip()
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, KeyError):
        return ''
    k = text.rfind('SCENE:')
    return text[k + 6:].strip().splitlines()[0].strip(' "*')[:400] if k >= 0 and text[k + 6:].strip() else ''


def theme_search(base, q, limit, ctx):
    url = base.rstrip('/') + '/api/passages/theme-search?' + urllib.parse.urlencode({'q': q, 'limit': limit})
    req = urllib.request.Request(url, headers={'User-Agent': 'Tesserae event builder'})
    if not url.startswith(('http://', 'https://')):
        raise ValueError('base must be http or https')
    with urllib.request.urlopen(req, timeout=180, context=ctx) as r:  # nosec B310 - scheme checked above
        return json.loads(r.read()).get('results') or []


def header(ev):
    return ('EVENT: %s\nDate: %s\nPlace: %s\nParticipants: %s\nSummary: %s\n'
            % (ev['label'], year_text(ev['ds']), ev.get('place_ancient') or ev.get('place') or '',
               ', '.join(ev['participants']), ev.get('summary') or ev.get('description') or ''))


def block(n, c):
    out = ['PASSAGE %d [%s, %s]' % (n, c['ref_start'], c['language'])]
    if c.get('gist'):
        out.append('Index description: ' + c['gist'])
    for ln in c['lines'][:3]:
        out.append('%s: %s' % (ln['ref'], str(ln['text'])[:400]))
    return '\n'.join(out)


def parse_labels(content, n):
    got = {}
    for m in re.finditer(r'"n"\s*:\s*"?(\d+)"?\s*,\s*"label"\s*:\s*"(yes|mention|no)"', content or '', re.I):
        got[int(m.group(1))] = m.group(2).lower()
    return [got.get(i + 1) for i in range(n)]


def judge(url, key, ev, batch):
    user = header(ev) + '\n' + '\n\n'.join(block(i + 1, c) for i, c in enumerate(batch))
    body = json.dumps({'model': J.MODEL, 'temperature': 0, 'max_tokens': 3500,
                       'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}],
                       **J.EXTRA_FIELDS}).encode()
    req = urllib.request.Request(url + '/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    if not req.full_url.startswith(('http://', 'https://')):
        raise ValueError('gateway URL must be http or https')
    for _ in range(5):
        try:
            with urllib.request.urlopen(req, timeout=240) as r:  # nosec B310 - scheme checked above
                return json.loads(r.read())['choices'][0]['message']['content'] or ''
        except urllib.error.HTTPError as e:
            if e.code == 402:
                raise J.QuotaStop('HTTP 402')
            time.sleep(J.RETRY_429_SECONDS if e.code == 429 else 5)
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(5)
    return ''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--cache', required=True)
    ap.add_argument('--event', action='append', default=[])
    ap.add_argument('--limit', type=int, default=30)
    ap.add_argument('--base', default='https://tesserae.caset.buffalo.edu')
    ap.add_argument('--cafile', help='certificate list for the live site (certifi works when the system list does not)')
    ap.add_argument('--texts')
    ap.add_argument('--window-texts')
    ap.add_argument('--extra-query', action='append', default=[],
                    help='a further Theme Search query given by hand (recorded in the cache with the others)')
    ap.add_argument('--report')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    if os.path.realpath(a.output).startswith('/var/www'):
        sys.exit('refusing to write under /var/www')
    if a.window_texts:
        os.environ['TESSERAE_WINDOW_TEXTS'] = a.window_texts
    from backend.blueprints import events as E
    if a.texts:
        E.TEXTS_ROOT = a.texts
    ctx = ssl.create_default_context(cafile=a.cafile) if a.cafile else None
    src = sqlite3.connect('file:%s?mode=ro' % a.input, uri=True)
    src.row_factory = sqlite3.Row
    cols = {r[1] for r in src.execute('PRAGMA table_info(events)')}
    evs = []
    for r in src.execute('SELECT * FROM events ORDER BY id'):
        if a.event and r['id'] not in a.event:
            continue
        evs.append({'id': r['id'], 'label': r['label'], 'ds': r['date_start'], 'de': r['date_end'],
                    'place': r['place'], 'place_ancient': r['place_ancient'] if 'place_ancient' in cols else None,
                    'participants': json.loads(r['participants'] or '[]'),
                    'description': r['description'], 'summary': r['summary'] if 'summary' in cols else None})
    cache = sqlite3.connect(a.cache)
    cache.execute('CREATE TABLE IF NOT EXISTS labels (event TEXT, window_id TEXT, label TEXT, model TEXT, prompt TEXT, '
                  'ts TEXT, PRIMARY KEY (event, window_id, prompt))')
    cache.execute('CREATE TABLE IF NOT EXISTS searches (event TEXT PRIMARY KEY, query TEXT, results TEXT, ts TEXT)')
    url = key = None
    added, report = {}, {'events': 0, 'candidates': 0, 'overlapping': 0, 'judged': 0, 'yes': 0, 'mention': 0, 'no': 0,
                         'unlabelled': 0, 'added': 0, 'per_event': []}
    for ev in evs:
        if ev['ds'] is None:
            continue
        report['events'] += 1
        row = cache.execute('SELECT results FROM searches WHERE event = ?', (ev['id'],)).fetchone()
        if row:
            results = json.loads(row[0])
        else:
            if url is None:
                url, key = J._env()
            qs = queries_for(ev) + [q for q in [scene_query(url, key, ev)] if q] + list(a.extra_query)
            results, ids = [], set()
            for q in qs:
                for res in theme_search(a.base, q, a.limit, ctx):
                    if res.get('id') not in ids:
                        ids.add(res.get('id'))
                        results.append(res)
            cache.execute('INSERT OR REPLACE INTO searches VALUES (?,?,?,?)',
                          (ev['id'], ' | '.join(qs), json.dumps(results, ensure_ascii=False),
                           time.strftime('%Y-%m-%d %H:%M:%S')))
            cache.commit()
        have = {}
        for p in src.execute('SELECT work, ref_start, ref_end, language FROM passages WHERE event_id = ?', (ev['id'],)):
            refs = {ln['ref'] for ln in E._passage_lines(p['work'], p['language'], p['ref_start'], p['ref_end'])}
            have.setdefault(base_work(p['work']), set()).update(refs)
        cands, seen = [], set()
        for res in results:
            w = base_work(res.get('work'))
            lines = E._passage_lines(res.get('work'), res.get('language'), res.get('ref_start'), res.get('ref_end'))
            refs = {ln['ref'] for ln in lines}
            report['candidates'] += 1
            if not lines or refs & have.get(w, set()) or refs & seen:
                report['overlapping'] += 1
                continue
            seen |= refs
            cands.append({'window_id': res.get('id'), 'work': w, 'ref_start': res.get('ref_start'),
                          'ref_end': res.get('ref_end'), 'language': res.get('language'), 'gist': res.get('gist'),
                          'lines': lines})
        labels = {r[0]: r[1] for r in cache.execute('SELECT window_id, label FROM labels WHERE event = ? AND prompt = ?',
                                                   (ev['id'], PROMPT_VERSION))}
        todo = [c for c in cands if c['window_id'] not in labels]
        for i in range(0, len(todo), BATCH):
            if url is None:
                url, key = J._env()
            batch = todo[i:i + BATCH]
            got = parse_labels(judge(url, key, ev, batch), len(batch))
            # A batch whose reply ran out before its JSON is asked again one passage at a time.
            for k, c in enumerate(batch):
                if not got[k]:
                    got[k] = parse_labels(judge(url, key, ev, [c]), 1)[0]
            for c, lab in zip(batch, got):
                if lab:
                    labels[c['window_id']] = lab
                    cache.execute('INSERT OR REPLACE INTO labels VALUES (?,?,?,?,?,?)',
                                  (ev['id'], c['window_id'], lab, J.MODEL, PROMPT_VERSION, time.strftime('%Y-%m-%d %H:%M:%S')))
            cache.commit()
        n_add = 0
        for c in cands:
            lab = labels.get(c['window_id'])
            report['judged'] += 1
            report[lab or 'unlabelled'] += 1
            if lab in ('yes', 'mention'):
                added.setdefault(ev['id'], []).append(dict(c, label=lab))
                n_add += 1
        report['added'] += n_add
        report['per_event'].append({'event': ev['id'], 'label': ev['label'], 'added': n_add,
                                    'passages': [(c['work'], c['ref_start'], labels.get(c['window_id'])) for c in cands]})
        print('%s %s: %d candidates, %d new, %d added' % (ev['id'], ev['label'], len(results), len(cands), n_add), flush=True)
    if a.report:
        with open(a.report, 'w') as f:
            json.dump(report, f, indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in report.items() if k != 'per_event'}))
    if not a.apply:
        print('dry run, no store written')
        return 0
    shutil.copyfile(a.input, a.output)
    dst = sqlite3.connect(a.output)
    pcols = [r[1] for r in dst.execute('PRAGMA table_info(passages)')]
    if 'found_by' not in pcols:
        dst.execute('ALTER TABLE passages ADD COLUMN found_by TEXT')
    from backend.blueprints import events as E2
    for eid, items in added.items():
        top = dst.execute('SELECT MAX(CAST(rank AS INTEGER)) FROM passages WHERE event_id = ?', (eid,)).fetchone()[0] or 0
        # The name forms already recorded on the event's passages ("Marcus Vipsanius Agrippa
        # [participant] = Ἀγρίππας"), looked for in each new passage, so its card shows the
        # line that names the event's people or place, not its first line.
        known = {}
        for (nm,) in dst.execute('SELECT names_matched FROM passages WHERE event_id = ?', (eid,)):
            for n in json.loads(nm or '[]'):
                if ' = ' in str(n):
                    head, forms = str(n).rsplit(' = ', 1)
                    for f in forms.split(','):
                        if f.strip():
                            known.setdefault(E2._fold(f.strip()), (head, f.strip()))
        # The event's own place by its stem, capitalized, in Latin letters ("Actium" finds
        # Actium, Actio, Actiacos), since the recorded forms rarely hold the place itself.
        ev_row = dst.execute('SELECT place, place_ancient FROM events WHERE id = ?', (eid,)).fetchone()
        place = (ev_row[1] or ev_row[0] or '') if ev_row else ''
        stem = E2._fold(place)[:-2] if len(place) >= 6 and ' ' not in place.strip() else ''
        for k, c in enumerate(items, 1):
            found = {}
            if stem:
                for ln in c['lines']:
                    for m in re.finditer(r'\b[A-Z][a-z]+', unicodedata.normalize('NFC', str(ln.get('text') or ''))):
                        w = m.group(0)
                        if E2._fold(w).startswith(stem) and len(w) <= len(place) + 5:
                            found.setdefault('%s [place]' % place, set()).add(w)
            for ln in c['lines']:
                text = unicodedata.normalize('NFC', str(ln.get('text') or ''))
                for m in re.finditer(r'(?:[^\W\d_]|[\u0300-\u036f])+', text):
                    hit = known.get(E2._fold(m.group(0)))
                    if hit:
                        found.setdefault(hit[0], set()).add(m.group(0))
            names = ['%s = %s' % (head, ', '.join(sorted(fs))) for head, fs in found.items()]
            first = ' '.join(str(c['lines'][0]['text']).split())
            snippet = first if len(first) <= 200 else first[:first.rfind(' ', 0, 200)] + ' …'
            dst.execute('INSERT INTO passages (event_id, rank, work, ref_start, ref_end, score, llm_label, names_matched, '
                        'snippet, window_id, language, found_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                        (eid, str(top + k), c['work'], c['ref_start'], c['ref_end'], None, c['label'],
                         json.dumps(names, ensure_ascii=False),
                         snippet, c['window_id'], c['language'], FOUND_BY))
    dst.commit()
    print('written', a.output, 'passages added', sum(len(v) for v in added.values()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
