#!/usr/bin/env python3
"""Choose the name an English-language classical scholar uses for each event's place, and write events.place_ancient.

  choose_place_names.py INPUT.sqlite OUTPUT.sqlite RAW_DIR --cache CACHE.sqlite
                        [--report PATH] [--sample-out PATH] [--limit N] [--apply]

For every event with a Pleiades place the script lists the place's qualifying names (add_place_ancient.py:
geographic, accurately transcribed, language Latin, English, none given or Ancient Greek, romanized form in Latin
letters) with the periods in which each is attested, with no requirement that a period overlaps the event.
The free BullsAI gateway model (the access rules and key file of judge_scholarship_relevance.py) is asked one question
per event and answers with one candidate exactly as written or NONE. Answers are kept in the table `answers` of the
cache file, keyed by event and a hash of the question, so a rerun costs nothing. A hand override table (OVERRIDES,
each with its reason) is applied after the model. A chosen name takes its standard English form from ENGLISH_FORMS, and the event title's spelling when the two
differ only by transliteration (title_spelling).
An answer that is not a candidate is asked once more and then counted as invalid and left empty. INPUT is never
modified. Dry run (cache filled, report written, no store) unless --apply. OUTPUT may not be under /var/www.
At most 8 requests are in flight. A 429 is retried after 30 seconds, a 402 or quota message stops the run with the
answers so far kept.
"""
import argparse
import csv
import hashlib
import json
import os
import random
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import add_place_ancient as A  # noqa: E402
import judge_scholarship_relevance as J  # noqa: E402

MAX_TOKENS = 700
RETRY_TOKENS = 2000

SYSTEM = ('You are a classical scholar. You are given an event, its year, the modern name of its place and the '
          'candidate ancient names of the place with the periods in which each is attested. Choose the one name that '
          'an English-language classical scholar would use for this place when writing about an event of that year. '
          'Prefer the Latin form in ordinary English use (Tarentum, Pherae, Caesarea) unless a Greek form is the one '
          'English uses for that time and place. Do not choose a regional name for a city, a long descriptive name '
          'for a short one in common use, a name with a colonial title or epithet (write Calagurris, not Calagurris '
          'Nassica Iulia), or a name out of use at the time. A candidate that is the same as the modern name is fine '
          'when scholars use that name for the place at that date (Dijon, Pisa). Answer with one candidate '
          'exactly as written, or NONE only if every candidate was out of use at that date or names a region or '
          'another kind of place. Think in at most three short sentences, then end with a '
          'last line of the form ANSWER: <candidate or NONE>.')

# Hand overrides, applied after the model's choice (the project lead, 2026-10-20). Each is
# (Pleiades id, first year, last year, name, reason). An event whose place has this id and whose years lie within the
# range takes the name whatever the model said.
OVERRIDES = [
    ('541044', -1000, 600, 'Pherae', 'Pleiades dates the Latin Pherae only from 30 BCE, yet English scholarship writes Pherae for the Thessalian city at every date.'),
    ('629035', 17, 400, 'Caesarea', 'Mazaka was renamed Eusebeia and then Caesarea (under Tiberius), and Caesarea is the name in use in the third century.'),
    ('226546', -700, 400, 'Olbia', 'Olbia is the common English name of the Pontic city, and the Pleiades Latin tag on Olbiopolis is a mistake.'),
    ('462410', -700, 700, 'Panormus', 'Panormus is the Latin name in English use, and the Pleiades Latin tag on Panormo is a mistake.'),
    ('668182', -1200, -300, 'Hamath', 'Hamath is the English name of the Syrian city under the Assyrians, and Pleiades has the modern Arabic Hama untagged.'),
    ('912849', -1200, 600, 'Euphrates', 'Euphrates is the English name of the river at every date, and the untagged Buranun and Purattu are Akkadian forms.'),
    ('177489', 300, 700, 'Dijon', 'Scholars write Dijon for the Burgundian town of late antiquity, not the descriptive Castrum Divionense.'),
    ('246279', -300, 400, 'Calagurris', 'Scholars write Calagurris for the Spanish town, without the colonial epithets Nassica Iulia.'),
    ('413225', -300, 600, 'Narnia', 'Narnia is the name of the town from the third century BCE on, and Nequinum went out of use then.'),
]


# Events whose stored Pleiades place is wrong (the project lead, 2026-10-21). Each is
# (event id, Pleiades id, ancient name, modern name, reason). The Pleiades id, name and modern place are set
# whatever the model said, so a rerun keeps them.
EVENT_PLACES = [
    ('Q160387', '530771', 'Actium', 'Aktio', 'Wikidata gives the Ionian Sea (Pleiades Ionium Mare) for the battle of 31 BCE, fought off the promontory of Actium.'),
    ('Q1892581', '432808', 'Cumae', 'Cuma', 'Wikidata gives the Bay of Naples (Pleiades Puteolanus Sinus) for the sea battle of 474 BCE off Cumae.'),
    ('Q960915', '413248', 'Perusia', 'Perugia', 'Wikidata gives no Pleiades place for the siege of Perusia of 41 to 40 BCE.'),
]


def event_year_text(y):
    return '%d %s' % (abs(y), 'BCE' if y < 0 else 'CE')


def years_text(rng):
    a, b = rng
    return '%s to %s' % (event_year_text(a), event_year_text(b))


def qualifying_names(place, periods):
    """[{'form', 'language', 'periods': [(key, [from, to])]}] for the qualifying names, one per form, in Pleiades order."""
    out, seen = [], {}
    for n in place.get('names') or []:
        if n.get('nameType') != 'geographic' or n.get('transcriptionAccuracy') == 'inaccurate':
            continue
        if (n.get('language') or '') not in A.LANG_RANK:
            continue
        form = A.first_variant(n.get('romanized'))
        if not A.latin_letters(form):
            continue
        keys = []
        for att in n.get('attestations') or []:
            k = att.get('timePeriod')
            if k in periods and (k, periods[k]) not in keys:
                keys.append((k, periods[k]))
        if form in seen:
            for kv in keys:
                if kv not in seen[form]['periods']:
                    seen[form]['periods'].append(kv)
            continue
        seen[form] = {'form': form, 'language': n.get('language') or '', 'periods': keys}
        out.append(seen[form])
    return out


def question(label, ds, de, modern, cands):
    when = event_year_text(ds) if ds == de else '%s to %s' % (event_year_text(ds), event_year_text(de))
    lines = []
    for c in cands:
        att = '; '.join('%s (%s)' % (k, years_text(r)) for k, r in c['periods']) or 'no period given'
        lines.append('- %s [attested: %s]' % (c['form'], att))
    return 'Event: %s\nYear: %s\nModern place name: %s\nCandidate names:\n%s' % (label, when, modern or '(none)', '\n'.join(lines))


def ask(url, key, user, stats, lock, max_tokens=MAX_TOKENS):
    body = json.dumps({'model': J.MODEL, 'temperature': 0, 'max_tokens': max_tokens,
                       'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}],
                       **J.EXTRA_FIELDS}).encode()
    req = urllib.request.Request(url + '/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
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


def clean_answer(text, forms):
    """The candidate named on the last ANSWER: line of the reply, 'NONE', or None when it names neither."""
    t = (text or '')
    k = t.rfind('ANSWER:')
    if k < 0:
        return None
    t = t[k + 7:].strip().splitlines()[0].strip().strip('`"\'*. ').strip() if t[k + 7:].strip() else ''
    t = t.split(' [attested')[0].strip()
    if t.upper() == 'NONE':
        return 'NONE'
    if t in forms:
        return t
    return t + '.' if t + '.' in forms else None


ABBREVIATIONS = ((' L.', 'Lacus '), (' M.', 'Mons '), (' Fl.', 'Flumen '))


def expand(name):
    """'Brigantinus L.' as the Latin 'Lacus Brigantinus' (Pleiades abbreviates the kind of place after the name)."""
    if name.startswith('Col. '):  # a colonial title is not part of the name scholars write
        name = name[5:]
    for suffix, word in ABBREVIATIONS:
        if name.endswith(suffix):
            return word + name[:-len(suffix)]
    return name


def spelling_key(word):
    """A key under which the Greek and Latinized spellings of one name agree (Themiskyra, Themiscyra)."""
    w = A.ascii_fold(word).lower()
    w = w.replace('k', 'c').replace('oe', 'e').replace('ae', 'e').replace('ai', 'e').replace('oi', 'e')
    w = re.sub(r'(.)\1', r'\1', w)
    for a, b in (('os', 'us'), ('on', 'um')):
        if w.endswith(a):
            w = w[:-len(a)] + b
    return w


def latin_score(word):
    """Higher for the Latinized spelling English scholars write (c for k, ae for ai, -us and -um for -os and -on)."""
    w = A.ascii_fold(word).lower()
    score = w.count('ae') + w.count('oe') - w.count('k') - w.count('ai') - w.count('oi')
    if w.endswith(('us', 'um', 'ae')):
        score += 1
    if w.endswith(('os', 'on', 'ai', 'oi')):
        score -= 1
    return score


def title_spelling(label, name):
    """The event title's own spelling of a one-word chosen name when the two differ only by transliteration.

    English Wikipedia titles mostly use the Latinized form scholars write (Siege of Themiscyra, Battle of Sphacteria),
    where the model often answered with the Greek transliteration in Pleiades (Themiskyra, Sphakteria). The title wins
    in that case only, and only toward the Latinized form (latin_score), so a title naming a modern place (Battle of the
    Ebro) or a Greek spelling (Battle of Korkyra, Battle of Uskana) never replaces the chosen name."""
    core = name[5:] if name.startswith('Mons ') else name
    if ' ' in core:
        return name
    key = spelling_key(core)
    for w in re.findall(r"[^\W\d_]+", label or ''):
        if w[:1].isupper() and w != core and spelling_key(w) == key and latin_score(w) > latin_score(core):
            return name.replace(core, w)
    return name


def override_for(pid, year_lo, year_hi):
    for opid, lo, hi, name, reason in OVERRIDES:
        if opid == pid and lo <= year_lo and year_hi <= hi:
            return name, reason
    return None


def apply_event_places(con):
    """Write EVENT_PLACES into an events table. Returns the number of events changed."""
    n = 0
    for eid, pid, name, modern, _reason in EVENT_PLACES:
        n += con.execute('UPDATE events SET pleiades_id = ?, place_ancient = ?, place = ? WHERE id = ?',
                         (pid, name, modern, eid)).rowcount
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('raw_dir')
    ap.add_argument('--cache', required=True)
    ap.add_argument('--report')
    ap.add_argument('--sample-out')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args(argv)
    if os.path.realpath(a.output).startswith('/var/www'):
        sys.exit('refusing to write under /var/www')
    periods = json.load(open(os.path.join(a.raw_dir, 'periods.json')))
    src = sqlite3.connect('file:%s?mode=ro' % a.input, uri=True)
    rows = src.execute("SELECT id, label, date_start, date_end, place, pleiades_id FROM events "
                       "WHERE pleiades_id IS NOT NULL AND pleiades_id <> '' ORDER BY id").fetchall()
    cache = sqlite3.connect(a.cache)
    cache.execute('CREATE TABLE IF NOT EXISTS answers (event_id TEXT, question_sha TEXT, question TEXT, answer TEXT, '
                  'model TEXT, ts TEXT, PRIMARY KEY (event_id, question_sha))')
    jobs = []
    for eid, label, ds, de, place, pid in rows:
        path = os.path.join(a.raw_dir, 'places', pid + '.json')
        if not os.path.exists(path) or ds is None or de is None:
            continue
        pl = json.load(open(path))
        cands = qualifying_names(pl, periods) if 'names' in pl else []
        jobs.append({'id': eid, 'label': label, 'ds': min(ds, de), 'de': max(ds, de), 'place': place, 'pid': pid,
                     'cands': cands, 'q': question(label, min(ds, de), max(ds, de), place, cands) if cands else None})
    if a.limit:
        jobs = jobs[:a.limit]
    for j in jobs:
        j['sha'] = hashlib.sha1((J.MODEL + SYSTEM + (j['q'] or '')).encode()).hexdigest()[:16] if j['q'] else None
    have = {(r[0], r[1]) for r in cache.execute('SELECT event_id, question_sha FROM answers')}
    todo = [j for j in jobs if j['q'] and (j['id'], j['sha']) not in have]
    stats = {'requests': 0, 'n429': 0, 'errors': 0, 'asked': len(todo)}
    print('events %d, with candidates %d, to ask %d' % (len(jobs), sum(1 for j in jobs if j['q']), len(todo)), flush=True)
    if todo:
        url, key = J._env()
        lock, stop = threading.Lock(), []

        def work(j):
            if stop:
                return None
            try:
                forms = {c['form'] for c in j['cands']}
                text = ask(url, key, j['q'], stats, lock)
                if clean_answer(text, forms) is None:  # not a candidate, ask once more
                    text = ask(url, key, j['q'], stats, lock, RETRY_TOKENS) or text
                return j, text
            except J.QuotaStop as e:
                stop.append(str(e))
                return None

        with ThreadPoolExecutor(J.MAX_IN_FLIGHT) as ex:
            for n, res in enumerate(ex.map(work, todo)):
                if res:
                    j, text = res
                    cache.execute('INSERT OR REPLACE INTO answers VALUES (?,?,?,?,?,?)',
                                  (j['id'], j['sha'], j['q'], text if text is not None else '', J.MODEL,
                                   time.strftime('%Y-%m-%d %H:%M:%S')))
                    if n % 50 == 0:
                        cache.commit()
                        print('  %d of %d' % (n + 1, len(todo)), flush=True)
        cache.commit()
        if stop:
            print('stopped: ' + stop[0], file=sys.stderr)
            return 3
    answers = {(r[0], r[1]): r[2] for r in cache.execute('SELECT event_id, question_sha, answer FROM answers')}
    chosen, detail = {}, []
    rep = {'events_with_pleiades': len(jobs), 'no_candidates': 0, 'asked_total': 0, 'model_none': 0, 'invalid': 0,
           'overridden': 0, 'named': 0, 'empty': 0, 'title_spelling': 0}
    for j in jobs:
        if not j['cands']:
            rep['no_candidates'] += 1
            rep['empty'] += 1
            continue
        rep['asked_total'] += 1
        forms = {c['form'] for c in j['cands']}
        ans = clean_answer(answers.get((j['id'], j['sha'])), forms)
        name, how, reason = None, 'model', ''
        if ans is None:
            rep['invalid'] += 1
            how = 'invalid'
        elif ans == 'NONE':
            rep['model_none'] += 1
            how = 'none'
        else:
            name = expand(A.english(ans))
            spelled = title_spelling(j['label'], name)
            if spelled != name:
                rep['title_spelling'] += 1
                name = spelled
        ov = override_for(j['pid'], j['ds'], j['de'])
        if ov:
            name, reason, how = ov[0], ov[1], 'override'
            rep['overridden'] += 1
        if name:
            chosen[j['id']] = name
            rep['named'] += 1
        else:
            rep['empty'] += 1
        detail.append({'job': j, 'name': name, 'how': how, 'reason': reason, 'model': ans})
    rep['answer_rate'] = round(1 - rep['invalid'] / max(rep['asked_total'], 1), 4)
    rep['same_as_modern'] = sum(1 for d in detail if d['name'] and d['job']['place'] and A.ascii_fold(d['job']['place']).lower() == d['name'].lower())
    rep['heading_changes'] = rep['named'] - rep['same_as_modern']
    rep['gateway'] = stats
    if a.report:
        with open(a.report, 'w') as f:
            json.dump({'summary': rep, 'events': [{'id': d['job']['id'], 'label': d['job']['label'], 'year': [d['job']['ds'], d['job']['de']],
                                                  'modern': d['job']['place'], 'name': d['name'], 'how': d['how'], 'model': d['model'],
                                                  'reason': d['reason'], 'candidates': [c['form'] for c in d['job']['cands']]}
                                                 for d in detail]}, f, indent=1, ensure_ascii=False)
    if a.sample_out:
        changing = [d for d in detail if d['name'] and not (d['job']['place'] and A.ascii_fold(d['job']['place']).lower() == d['name'].lower())]
        rnd = random.Random(60)
        pick = rnd.sample(changing, min(60, len(changing)))
        os.makedirs(os.path.dirname(a.sample_out), exist_ok=True)
        with open(a.sample_out, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['event', 'year', 'modern place', 'chosen name', 'how chosen', 'candidates', 'lead grade (right / wrong / better name)'])
            for d in pick:
                j = d['job']
                yr = event_year_text(j['ds']) if j['ds'] == j['de'] else '%s to %s' % (event_year_text(j['ds']), event_year_text(j['de']))
                w.writerow([j['label'], yr, j['place'], d['name'], d['how'], ' | '.join(c['form'] for c in j['cands']), ''])
    print(json.dumps({k: v for k, v in rep.items()}))
    if not a.apply:
        print('dry run, no store written')
        return 0
    import shutil
    shutil.copyfile(a.input, a.output)
    dst = sqlite3.connect(a.output)
    if 'place_ancient' not in [r[1] for r in dst.execute('PRAGMA table_info(events)')]:
        dst.execute('ALTER TABLE events ADD COLUMN place_ancient TEXT')
    dst.execute('UPDATE events SET place_ancient = NULL')
    for eid, nm in chosen.items():
        dst.execute('UPDATE events SET place_ancient = ? WHERE id = ?', (nm, eid))
    apply_event_places(dst)
    dst.commit()
    dst.close()
    print('written', a.output, len(chosen))
    return 0


if __name__ == '__main__':
    sys.exit(main())
