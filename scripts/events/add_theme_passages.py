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
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_scholarship_relevance as J  # noqa: E402

FOUND_BY = 'theme search 2026-10-21'
# The model of the 2026-10-09 judge (llm_judge.py DEFAULT_MODEL), so new labels are made as the old ones
# were. GLM-5.3-Flash, the first choice for Actium, returned HTTP 500 for every request on 2026-10-21 13:00.
MODEL = 'Qwen/Qwen3.8-27B-FP8'
EXTRA_FIELDS = {'chat_template_kwargs': {'enable_thinking': False}}
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
    body = json.dumps({'model': MODEL, 'temperature': 0, 'max_tokens': 1200,
                       'messages': [{'role': 'system', 'content': SCENE_SYSTEM},
                                    {'role': 'user', 'content': header(ev)}], **EXTRA_FIELDS}).encode()
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


NOTE_SYSTEM = ('You are a historian of the ancient world. In two plain sentences of at most 60 words, say what is '
               'known of the event you are given: who fought or negotiated, where, and how it ended. If you do not '
               'know the event, say only what its name and date imply and nothing more. End with a last line of '
               'the form NOTE: <the two sentences>.')


def note_for(url, key, ev):
    """Background for an event with no summary (459 events have neither a summary nor an English
    Wikipedia article). Used only to search and to judge, never shown on the page."""
    body = json.dumps({'model': MODEL, 'temperature': 0, 'max_tokens': 600,
                       'messages': [{'role': 'system', 'content': NOTE_SYSTEM},
                                    {'role': 'user', 'content': header(ev)}], **EXTRA_FIELDS}).encode()
    req = urllib.request.Request(url + '/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    if not req.full_url.startswith(('http://', 'https://')):
        raise ValueError('gateway URL must be http or https')
    try:
        with urllib.request.urlopen(req, timeout=180) as r:  # nosec B310 - scheme checked above
            text = (json.loads(r.read())['choices'][0]['message']['content'] or '').strip()
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, KeyError):
        return ''
    k = text.rfind('NOTE:')
    return text[k + 5:].strip()[:500] if k >= 0 else ''


VERIFY_SYSTEM = (
    "You are a historian of the ancient world who reads Greek and Latin. You are given one historical EVENT and "
    "one PASSAGE. Decide whether the passage is about THIS event: it narrates it, or it refers to this particular "
    "event (this battle, siege or treaty, at this place and date), not another battle, siege or treaty that "
    "resembles it, and not the same people or places on another occasion. Answer YES or NO. If YES, quote the "
    "words of the passage, in its own language and at most twelve words, that show it is this event. End with "
    "two last lines: ANSWER: YES or ANSWER: NO, and QUOTE: <the words, or nothing>.")


def verify(url, key, ev, c):
    """A stricter second reading of an added passage, with its lines in full. Kept only when the model
    says YES and the words it quotes are in the passage (2026-10-21: of 54 additions on 20 sampled
    events about a third were another event of the same kind, Petrarch and Polybius under Veii)."""
    lines = '\n'.join('%s: %s' % (ln['ref'], str(ln['text'])[:500]) for ln in c['lines'][:14])
    user = header(ev) + '\nPASSAGE [%s, %s]\n%s' % (c['ref_start'], c['language'], lines)
    body = json.dumps({'model': MODEL, 'temperature': 0, 'max_tokens': 900,
                       'messages': [{'role': 'system', 'content': VERIFY_SYSTEM}, {'role': 'user', 'content': user}],
                       **EXTRA_FIELDS}).encode()
    req = urllib.request.Request(url + '/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    if not req.full_url.startswith(('http://', 'https://')):
        raise ValueError('gateway URL must be http or https')
    try:
        with urllib.request.urlopen(req, timeout=180) as r:  # nosec B310 - scheme checked above
            text = json.loads(r.read())['choices'][0]['message']['content'] or ''
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, KeyError):
        return None, ''
    m = re.search(r'ANSWER:\s*(YES|NO)', text, re.I)
    q = re.search(r'QUOTE:\s*(.*)', text)
    quote = (q.group(1).strip().strip('"\'«»“”') if q else '')[:200]
    return (m.group(1).upper() if m else None), quote


def quote_in(quote, lines):
    """True when the quoted words occur, in order, in the passage (accents and case ignored)."""
    from backend.blueprints import events as E
    words = [E._fold(w) for w in re.findall(r'(?:[^\W\d_]|[\u0300-\u036f])+', unicodedata.normalize('NFC', quote))]
    if len(words) < 2:
        return False
    text = ' '.join(E._fold(w) for ln in lines for w in re.findall(
        r'(?:[^\W\d_]|[\u0300-\u036f])+', unicodedata.normalize('NFC', str(ln.get('text') or ''))))
    return ' '.join(words) in text


def theme_search(base, q, limit, ctx, reader=True):
    args = {'q': q, 'limit': limit}
    if not reader:
        args['reader'] = '0'   # description ranking only: the reader service is not loaded by a bulk run
    url = base.rstrip('/') + '/api/passages/theme-search?' + urllib.parse.urlencode(args)
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
    body = json.dumps({'model': MODEL, 'temperature': 0, 'max_tokens': 3500,
                       'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}],
                       **EXTRA_FIELDS}).encode()
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
    ap.add_argument('--no-reader', action='store_true', help='Theme Search without its reader step (bulk runs)')
    ap.add_argument('--workers', type=int, default=8, help='judging requests in flight')
    ap.add_argument('--event-workers', type=int, default=1, help='events processed at once')
    ap.add_argument('--search-workers', type=int, default=1, help='Theme Searches at once on the live site')
    ap.add_argument('--sample', type=int, default=0, help='a random sample of this many events (seed 21)')
    ap.add_argument('--summary', help='a summary for the judge when the event has none (one event only)')
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
    # EVERY WORK READ ONCE. Each event looks up the lines of some 350 passages, and a work kept
    # in parts was read from its corpus files on every lookup, about five minutes an event at
    # six events at once (2026-10-21). The whole work is now read once and kept, then sliced.
    _work_lines, _work_lock = {}, threading.Lock()
    _original_lines = E._passage_lines

    def _all_lines(work, lang):
        key = (work, lang)
        with _work_lock:
            if key in _work_lines:
                return _work_lines[key]
        rows = []
        try:
            from backend import window_texts
            c = window_texts._conn()
            if c is not None:
                rows = [{'ref': r, 'text': t} for r, t in c.execute(
                    'SELECT ref, text FROM lines WHERE work = ? ORDER BY ord', (work,))]
        except Exception:                                # noqa: BLE001
            rows = []
        if not rows:
            import glob
            for lg in ([lang] if lang else []) + ['la', 'grc', 'en', 'he', 'cop', 'fa', 'ur']:
                whole = os.path.join(E.TEXTS_ROOT, lg, work + '.tess')
                parts = sorted(glob.glob(os.path.join(E.TEXTS_ROOT, lg, work + '.part.*.tess')),
                               key=lambda q: [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', q)])
                paths = [whole] if os.path.exists(whole) else parts
                if paths:
                    break
            else:
                paths = []
            for path in paths:
                with open(path, encoding='utf-8') as fh:
                    for raw in fh:
                        m = E._TESS_LINE.match(raw.strip())
                        if m:
                            rows.append({'ref': m.group(1), 'text': m.group(2)})
        index = {E._ref_key(r['ref']): i for i, r in enumerate(rows)}
        with _work_lock:
            _work_lines[key] = (rows, index)
        return rows, index

    def cached_lines(work, lang, ref_start, ref_end):
        rows, index = _all_lines(work, lang)
        i = index.get(E._ref_key(ref_start))
        if i is None:
            return _original_lines(work, lang, ref_start, ref_end)
        j = index.get(E._ref_key(ref_end or ref_start), i)
        return rows[i:max(i, j) + 1][:E.EXCERPT_LINES_CAP]

    E._passage_lines = cached_lines
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
    cache = sqlite3.connect(a.cache, check_same_thread=False)
    cache.execute('CREATE TABLE IF NOT EXISTS labels (event TEXT, window_id TEXT, label TEXT, model TEXT, prompt TEXT, '
                  'ts TEXT, PRIMARY KEY (event, window_id, prompt))')
    cache.execute('CREATE TABLE IF NOT EXISTS searches (event TEXT PRIMARY KEY, query TEXT, results TEXT, ts TEXT)')
    lock, search_lock = threading.Lock(), threading.Semaphore(max(1, a.search_workers))
    url, key = J._env()
    added, report = {}, {'events': 0, 'candidates': 0, 'overlapping': 0, 'judged': 0, 'yes': 0, 'mention': 0, 'no': 0,
                         'not verified': 0, 'unlabelled': 0, 'added': 0, 'per_event': []}

    cache.execute('CREATE TABLE IF NOT EXISTS notes (event TEXT PRIMARY KEY, note TEXT, model TEXT, ts TEXT)')
    cache.execute('CREATE TABLE IF NOT EXISTS verified (event TEXT, window_id TEXT, verdict TEXT, quote TEXT, model TEXT, '
                  'ts TEXT, PRIMARY KEY (event, window_id))')

    def process(ev):
        t0 = time.time()
        if not (ev.get('summary') or '').strip():
            with lock:
                got = cache.execute('SELECT note FROM notes WHERE event = ?', (ev['id'],)).fetchone()
            if got:
                ev['summary'] = got[0]
            else:
                ev['summary'] = note_for(url, key, ev)
                with lock:
                    cache.execute('INSERT OR REPLACE INTO notes VALUES (?,?,?,?)',
                                  (ev['id'], ev['summary'], MODEL, time.strftime('%Y-%m-%d %H:%M:%S')))
        with lock:
            row = cache.execute('SELECT results FROM searches WHERE event = ?', (ev['id'],)).fetchone()
        if row:
            results = json.loads(row[0])
        else:
            qs = queries_for(ev) + [q for q in [scene_query(url, key, ev)] if q] + list(a.extra_query)
            results, ids = [], set()
            with search_lock:   # at most --search-workers Theme Searches at a time on the live site
                for q in qs:
                    for res in theme_search(a.base, q, a.limit, ctx, reader=not a.no_reader):
                        if res.get('id') not in ids:
                            ids.add(res.get('id'))
                            results.append(res)
            if not results:
                # Nothing came back, which happens while the site restarts after a deploy: not cached,
                # so a rerun searches again (five events of the 2026-10-21 run hit the 14:52 restart).
                print('%s %s: Theme Search returned nothing, not cached' % (ev['id'], ev['label']), flush=True)
                return
            with lock:
                cache.execute('INSERT OR REPLACE INTO searches VALUES (?,?,?,?)',
                              (ev['id'], ' | '.join(qs), json.dumps(results, ensure_ascii=False),
                               time.strftime('%Y-%m-%d %H:%M:%S')))
                cache.commit()
        mine = sqlite3.connect('file:%s?mode=ro' % a.input, uri=True)
        have = {}
        # Only passages already shown block a candidate. One the 2026-10-09 judge called unrelated is
        # judged again when Theme Search finds it: for the Battle of Perugia, which had no summary,
        # that judge called Velleius 2.74 (Caesar's taking of Perusia) unrelated (2026-10-21).
        for w0, rs, re_, lang in mine.execute("SELECT work, ref_start, ref_end, language FROM passages "
                                             "WHERE event_id = ? AND COALESCE(llm_label, '') <> 'no'",
                                             (ev['id'],)):
            refs = {ln['ref'] for ln in E._passage_lines(w0, lang, rs, re_)}
            have.setdefault(base_work(w0), set()).update(refs)
        mine.close()
        cands, seen, overlapping = [], set(), 0
        for res in results:
            w = base_work(res.get('work'))
            lines = E._passage_lines(res.get('work'), res.get('language'), res.get('ref_start'), res.get('ref_end'))
            refs = {ln['ref'] for ln in lines}
            if not lines or refs & have.get(w, set()) or refs & seen:
                overlapping += 1
                continue
            seen |= refs
            cands.append({'window_id': res.get('id'), 'work': w, 'ref_start': res.get('ref_start'),
                          'ref_end': res.get('ref_end'), 'language': res.get('language'), 'gist': res.get('gist'),
                          'lines': lines})
        with lock:
            labels = {r[0]: r[1] for r in cache.execute(
                'SELECT window_id, label FROM labels WHERE event = ? AND prompt = ?', (ev['id'], PROMPT_VERSION))}
        todo = [c for c in cands if c['window_id'] not in labels]

        def one_batch(batch):
            got = parse_labels(judge(url, key, ev, batch), len(batch))
            # A batch whose reply ran out before its JSON is asked again one passage at a time.
            for k, c in enumerate(batch):
                if not got[k]:
                    got[k] = parse_labels(judge(url, key, ev, [c]), 1)[0]
            return batch, got

        batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
        with ThreadPoolExecutor(max(1, a.workers)) as pool:
            for batch, got in pool.map(one_batch, batches):
                for c, lab in zip(batch, got):
                    if lab:
                        labels[c['window_id']] = lab
                        with lock:
                            cache.execute('INSERT OR REPLACE INTO labels VALUES (?,?,?,?,?,?)',
                                          (ev['id'], c['window_id'], lab, MODEL, PROMPT_VERSION,
                                           time.strftime('%Y-%m-%d %H:%M:%S')))
        # The stricter second reading, for every passage the first labeled yes or mention.
        with lock:
            done = {r[0]: (r[1], r[2]) for r in cache.execute(
                'SELECT window_id, verdict, quote FROM verified WHERE event = ?', (ev['id'],))}
        to_verify = [c for c in cands if labels.get(c['window_id']) in ('yes', 'mention') and c['window_id'] not in done]

        def one_verify(c):
            return c, verify(url, key, ev, c)

        with ThreadPoolExecutor(max(1, a.workers)) as pool:
            for c, (verdict, quote) in pool.map(one_verify, to_verify):
                if verdict:
                    done[c['window_id']] = (verdict, quote)
                    with lock:
                        cache.execute('INSERT OR REPLACE INTO verified VALUES (?,?,?,?,?,?)',
                                      (ev['id'], c['window_id'], verdict, quote, MODEL, time.strftime('%Y-%m-%d %H:%M:%S')))
        for c in cands:
            if labels.get(c['window_id']) in ('yes', 'mention'):
                verdict, quote = done.get(c['window_id'], (None, ''))
                if not (verdict == 'YES' and quote_in(quote, c['lines'])):
                    labels[c['window_id']] = 'not verified'
        n_add = 0
        with lock:
            cache.commit()
            report['events'] += 1
            report['candidates'] += len(results)
            report['overlapping'] += overlapping
            for c in cands:
                lab = labels.get(c['window_id'])
                report['judged'] += 1
                report[lab or 'unlabelled'] += 1
                if lab in ('yes', 'mention'):
                    added.setdefault(ev['id'], []).append(dict(c, label=lab))
                    n_add += 1
            report['added'] += n_add
            report['per_event'].append({'event': ev['id'], 'label': ev['label'], 'added': n_add,
                                        'passages': [(c['work'], c['ref_start'], labels.get(c['window_id']))
                                                     for c in cands]})
        print('%s %s: %d candidates, %d new, %d added, %.0f s' % (ev['id'], ev['label'], len(results), len(cands),
                                                                  n_add, time.time() - t0), flush=True)

    if a.sample:
        import random
        evs = random.Random(21).sample(evs, min(a.sample, len(evs)))
    if a.summary:
        if len(evs) != 1:
            sys.exit('--summary needs exactly one --event')
        evs[0]['summary'] = a.summary
    todo_events = [ev for ev in evs if ev['ds'] is not None]
    with ThreadPoolExecutor(max(1, a.event_workers)) as pool:
        for fut in [pool.submit(process, ev) for ev in todo_events]:
            try:
                fut.result()
            except J.QuotaStop as e:
                print('stopped: %s' % e, file=sys.stderr)
                return 3
            except Exception as e:                       # noqa: BLE001
                print('event failed: %s' % e, file=sys.stderr, flush=True)
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
            for ln in c['lines']:
                text = unicodedata.normalize('NFC', str(ln.get('text') or ''))
                for m in re.finditer(r'(?:[^\W\d_]|[\u0300-\u036f])+', text):
                    hit = known.get(E2._fold(m.group(0)))
                    if hit:
                        found.setdefault(hit[0], set()).add(m.group(0))
            if stem:
                for ln in c['lines']:
                    for m in re.finditer(r'\b[A-Z][a-z]+', unicodedata.normalize('NFC', str(ln.get('text') or ''))):
                        w = m.group(0)
                        already = any(w in fs for fs in found.values())
                        if not already and E2._fold(w).startswith(stem) and len(w) <= len(place) + 5:
                            found.setdefault('%s [place]' % place, set()).add(w)
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
