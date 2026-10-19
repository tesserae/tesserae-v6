"""Stage 3a: a proper heading for every corpus name, and the frequent corpus names promoted to entities
after a gateway judgment (2026-10-17). Every step reads and writes files in --work-dir (private), so a
gateway step cut off by its time budget picks up where it stopped.

    venv/bin/python scripts/entity_promote.py STEP --store STAGE2B.sqlite --work-dir research/entities/stage3a_work \
        --passage-dir data/passage_index [--out STAGE3A.sqlite]

STEP, in order:
    prepare   choose the corpus names with at least 10 lines in at least 3 works and write one question each
              (spellings with counts, three lines from different works)               (tess-job, about 2 minutes)
    ask       send the questions to the campus gateway                                  (--budget SECONDS, resumable)
    collide   stage 4: the stem test on every corpus name, one question per qualifying group of a collision
              candidate (--budget SECONDS, resumable), the report of the keys the model splits
    greekfix  stage 4: ask whether the Greek label of a split is the Greek name of its Latin name, for the splits
              with a spelling of the key outside the main forms that has the label's stem (Carnutes and Κάρνοι)
    build     copy --store to --out, write display labels, promote and merge, rebuild the catalog
              (about 30 seconds, under 0.2 GB)
    draw      draw the fresh promoted entities for grading (--seed)
    stats     type counts and split counts of the judgments

The gateway address and key are read by backend/entity_gateway.py from the production .env and are never
printed or written. The judgments and questions stay in --work-dir; this script carries no data.
"""
import argparse
import collections
import json
import os
import random
import shutil
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend import entity_extras as extras  # noqa: E402
from backend import entity_gateway as gw  # noqa: E402
from backend import entity_model_pass as mp  # noqa: E402
from backend import entity_promote as pr  # noqa: E402

LANG_NAME = {'la': 'Latin', 'grc': 'Greek', 'en': 'English'}
SEED_SNIPPETS = 20261017


def p(a, name):
    return os.path.join(a.work_dir, name)


def read_jsonl(path):
    out = []
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            if line.strip():
                out.append(json.loads(line))
    return out


def ro(path):
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


# ------------------------------------------------------------------ prepare

def step_prepare(a):
    t0 = time.time()
    db = ro(a.store)
    tx = ro(os.path.join(a.passage_dir, 'window_texts.db'))
    chosen = pr.frequent_names(db)
    print(f'{len(chosen)} corpus names with at least {pr.MIN_LINES} lines in {pr.MIN_WORKS} works', flush=True)
    keys = dict(db.execute("select eid, name_key from entities where source = 'names'"))
    out = []
    no_line = 0
    for n, eid in enumerate(sorted(chosen, key=lambda e: keys[e])):
        key = keys[eid]
        forms = db.execute('select form, count(*) c from mention_rows where eid = ? group by form order by c desc, form',
                           (eid,)).fetchall()
        rows = db.execute('select w.work, w.language, m.form, m.line_ref from mention_rows m join windows w on w.wid = m.wid '
                          'where m.eid = ? and m.line_ref is not null order by m.wid', (eid,)).fetchall()
        by_work = collections.defaultdict(list)
        for work, lang, form, ref in rows:
            by_work[work].append((lang, form, ref))
        rnd = random.Random(f'{SEED_SNIPPETS}:{key}')
        works = sorted(by_work)
        rnd.shuffle(works)
        snippets = []
        for work in works:
            lang, form, ref = rnd.choice(by_work[work])
            r = tx.execute('select text from lines where work = ? and ref = ? limit 1', (work, ref)).fetchone()
            if not r or form not in r[0]:
                continue
            snippets.append([mp.author_of(work), LANG_NAME.get(lang, lang), mp.line_snippet(r[0], form, 160)])
            if len(snippets) == pr.SNIPPET_LINES:
                break
        if len(snippets) < pr.SNIPPET_LINES:
            no_line += 1
        out.append({'key': key, 'lines': chosen[eid][0], 'works': chosen[eid][1],
                    'forms': [[f, c] for f, c in forms[:pr.MAX_FORMS]], 'n_forms': len(forms), 'snippets': snippets})
        if n % 1000 == 0:
            print(f'  {n}/{len(chosen)}', flush=True)
    with open(p(a, 'questions.jsonl'), 'w', encoding='utf-8') as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(json.dumps({'questions': len(out), 'with_fewer_than_3_lines': no_line, 'seconds': round(time.time() - t0)}))


# ------------------------------------------------------------------ ask

def run_pool(a, todo, ask_fn, out_path, max_tokens=300):
    """Send `todo` (a list of items) through ask_fn(client, item) -> record, appending records to
    out_path. The first 200 run at 16 threads and the next 200 at 48 so the rate at each is
    measured, then --threads. Writes out_path.rates.json and out_path.gateway.json."""
    url, key = gw.load_config()
    client = gw.Gateway(url, key)
    rate_path = out_path + '.rates.json'
    rates = json.load(open(rate_path)) if os.path.exists(rate_path) else []
    seen16 = sum(r['n'] for r in rates if r['threads'] == 16)
    seen48 = sum(r['n'] for r in rates if r['threads'] == 48)
    t_start = time.time()
    pos = 0
    f = open(out_path, 'a', encoding='utf-8')
    try:
        while pos < len(todo) and time.time() - t_start < a.budget:
            if seen16 < 200:
                threads, count = 16, 200 - seen16
            elif seen48 < 200:
                threads, count = 48, 200 - seen48
            else:
                threads, count = a.threads, 480
            chunk = todo[pos:pos + count]
            t0 = time.time()
            n_bad = i = 0
            while i < len(chunk) and time.time() - t_start < a.budget:
                piece = chunk[i:i + max(threads * 4, 48)]
                results, _s = gw.run_jobs(piece, lambda it: ask_fn(client, it), threads)
                for r in results:
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
                    n_bad += r.get('answer') is None
                f.flush()
                i += len(piece)
            secs = time.time() - t0
            pos += i
            if i:
                rec = {'threads': threads, 'n': i, 'seconds': round(secs, 1), 'rps': round(i / max(secs, 1e-9), 2),
                       'no_answer': n_bad, 'at': time.strftime('%H:%M:%S')}
                rates.append(rec)
                json.dump(rates, open(rate_path, 'w'))
                print(json.dumps(rec), flush=True)
                if threads == 16:
                    seen16 += i
                elif threads == 48 and seen48 < 200:
                    seen48 += i
    finally:
        f.close()
    stats_path = out_path + '.gateway.json'
    prev = json.load(open(stats_path)) if os.path.exists(stats_path) else {}
    for k, v in client.stats.items():
        if k == 'errors':
            prev.setdefault('errors', {})
            for e, n in v.items():
                prev['errors'][e] = prev['errors'].get(e, 0) + n
        else:
            prev[k] = prev.get(k, 0) + v
    prev['seconds'] = round(prev.get('seconds', 0) + time.time() - t_start, 1)
    json.dump(prev, open(stats_path, 'w'))
    print(f'asked {pos} this run, {len(todo) - pos} still to ask, gateway {json.dumps(client.stats)}', flush=True)


def step_ask(a):
    questions = read_jsonl(p(a, 'questions.jsonl'))
    out_path = p(a, 'judgments.jsonl')
    done = {r['key']: r for r in read_jsonl(out_path)}
    todo = [q for q in questions if (done.get(q['key']) or {}).get('answer') is None]
    print(f'{len(questions)} questions, {len(questions) - len(todo)} answered, {len(todo)} to ask', flush=True)

    def ask(client, q):
        spellings = [f for f, _c in q['forms']]
        txt = client.ask(pr.SYSTEM, pr.question(q['key'], q['forms'], q['snippets']), max_tokens=300)
        ans = pr.parse_judgment(txt, spellings)
        # the record carries the key, the spellings and the answer, never a context line
        return {'key': q['key'], 'spellings': q['forms'], 'answer': ans, 'reply': txt if ans is None else None}

    run_pool(a, todo, ask, out_path)


# ------------------------------------------------------------------ the split fix (2026-10-17, second round)

def step_splitfix(a):
    """Ask again about every split whose main spellings share no start with its own label: which of
    the spellings belong to the label. Reads --store (the stage 2b store) for the lines."""
    j = load_judgments(a, fixes=False)
    forms = {r['key']: r['spellings'] for r in read_jsonl(p(a, 'judgments.jsonl')) if r.get('answer')}
    bad = sorted(k for k, x in j.items() if pr.contradicts_label(x))
    out_path = p(a, 'judgments_splitfix.jsonl')
    done = {r['key'] for r in read_jsonl(out_path) if r.get('answer') is not None}
    todo = [k for k in bad if k not in done]
    print(f'{len(bad)} splits contradict their label, {len(todo)} to ask', flush=True)
    db, tx = ro(a.store), ro(os.path.join(a.passage_dir, 'window_texts.db'))
    eids = dict(db.execute("select name_key, eid from entities where source = 'names'"))
    items = []
    for k in todo:
        items.append({'key': k, 'label': j[k]['latin'], 'type': j[k]['type'], 'forms': forms[k],
                      'snippets': pr.context_lines(db, tx, eids[k], 5, 'split')})

    def ask(client, it):
        txt = client.ask(pr.SPLIT_SYSTEM, pr.split_question(it['label'], it['type'], it['forms'], it['snippets']), max_tokens=400)
        ans = pr.parse_split(txt, [f for f, _c in it['forms']])
        return {'key': it['key'], 'label': it['label'], 'answer': ans, 'reply': txt if ans is None else None}

    run_pool(a, items, ask, out_path)


# ------------------------------------------------------------------ the label of a split (stage 3b)

def step_labelfix(a):
    """Ask for the label itself of every split whose main spellings still share no start with it:
    what name do these spellings spell. Reads --store (the stage 2b store) for the lines."""
    j = load_judgments(a, labelfix=False)
    forms = {r['key']: r['spellings'] for r in read_jsonl(p(a, 'judgments.jsonl')) if r.get('answer')}
    bad = pr.still_contradicts(j)
    out_path = p(a, 'judgments_labelfix.jsonl')
    done = {r['key'] for r in read_jsonl(out_path) if r.get('answer') is not None}
    todo = [k for k in bad if k not in done]
    print(f'{len(bad)} splits still contradict their label, {len(todo)} to ask', flush=True)
    db, tx = ro(a.store), ro(os.path.join(a.passage_dir, 'window_texts.db'))
    eids = dict(db.execute("select name_key, eid from entities where source = 'names'"))
    items = []
    for k in todo:
        main = j[k]['main_forms']
        counts = dict((f, c) for f, c in forms[k])
        items.append({'key': k, 'type': j[k]['type'], 'was': j[k]['latin'], 'forms': [[f, counts.get(f, 0)] for f in main],
                      'snippets': pr.context_lines(db, tx, eids[k], 5, 'label', only={ei_fold(f) for f in main})})

    def ask(client, it):
        txt = client.ask(pr.LABEL_SYSTEM, pr.label_question(it['type'], it['forms'], it['snippets']), max_tokens=200)
        ans = pr.parse_label(txt)
        return {'key': it['key'], 'was': it['was'], 'answer': None if ans is None else {'latin': ans[0], 'greek': ans[1]},
                'reply': txt if ans is None else None}

    run_pool(a, items, ask, out_path)


def ei_fold(x):
    from backend import entity_index as ei
    return ei.fold(x)


# ------------------------------------------------------------------ key collisions split by stem (stage 4)

def collision_groups_of_store(db):
    """{key: {stem: group}} for every corpus name of the store: the groups of its spellings by their first six
    transliterated letters, with the lines and works of each (entity_promote.collision_groups)."""
    rows_by_eid = collections.defaultdict(list)
    keys = dict(db.execute("select eid, name_key from entities where source = 'names'"))
    q = ("select m.eid, m.form, w.work, coalesce(m.line_ref, '#' || m.wid) from mention_rows m "
         "join windows w on w.wid = m.wid join entities e on e.eid = m.eid where e.source = 'names'")
    for eid, form, work, line in db.execute(q):
        rows_by_eid[eid].append((form, work, line))
    return {keys[eid]: pr.collision_groups(rows) for eid, rows in rows_by_eid.items()}


def collision_snippets(db, tx, eid, forms, n=3, tag='collide'):
    """Up to n lines from different works that hold one of the group's spellings: [author, language, line]."""
    wanted = set(forms)
    rnd = random.Random(f'{SEED_SNIPPETS}:{tag}:{min(wanted)}')
    by_work = collections.defaultdict(list)
    for work, lang, form, ref in db.execute(
            'select w.work, w.language, m.form, m.line_ref from mention_rows m join windows w on w.wid = m.wid '
            'where m.eid = ? and m.line_ref is not null order by m.wid', (eid,)):
        if form in wanted:
            by_work[work].append((lang, form, ref))
    works = sorted(by_work)
    rnd.shuffle(works)
    out = []
    for work in works:
        lang, form, ref = rnd.choice(by_work[work])
        r = tx.execute('select text from lines where work = ? and ref = ? limit 1', (work, ref)).fetchone()
        if not r or form not in r[0]:
            continue
        out.append([mp.author_of(work), LANG_NAME.get(lang, lang), mp.line_snippet(r[0], form, 160)])
        if len(out) == n:
            break
    return out


def step_collide(a):
    """The stem test (entity_promote.collision_candidate) over every corpus name of --store, then one question
    per qualifying group of each candidate: the stage 3a question (entity_promote.question and parse_judgment)
    asked about the group's own spellings and three lines that hold them. A group whose spellings are exactly
    the main forms of the key's earlier judgment takes that judgment and is not asked again."""
    t0 = time.time()
    db, tx = ro(a.store), ro(os.path.join(a.passage_dir, 'window_texts.db'))
    groups = collision_groups_of_store(db)
    print(f'{len(groups)} corpus-name keys, groups computed {time.time() - t0:.0f}s', flush=True)
    cand = {k: pr.collision_candidate(g) for k, g in groups.items()}
    cand = {k: g for k, g in cand.items() if g}
    old = {}
    for r in read_jsonl(p(a, 'judgments.jsonl')):
        if r.get('answer'):
            old[r['key']] = r['answer']
    judged = [k for k in cand if k in old]
    eids = dict(db.execute("select name_key, eid from entities where source = 'names'"))
    json.dump({k: g for k, g in cand.items()}, open(p(a, 'collide_candidates.json'), 'w'), ensure_ascii=False)
    print(f'{len(cand)} collision candidates ({len(judged)} of them keys the stage 3a pass judged), '
          f'{sum(len(g) for g in cand.values())} qualifying groups', flush=True)
    out_path = p(a, 'collide_judgments.jsonl')
    done = {(r['key'], r['group']) for r in read_jsonl(out_path) if r.get('answer') is not None}
    items = []
    reused = []
    for k, g in sorted(cand.items()):
        for st, grp in sorted(g.items()):
            if (k, st) in done:
                continue
            o = old.get(k)
            if o and o['distinct_names'] and o['main_forms'] and set(o['main_forms']) == set(grp['forms']):
                reused.append({'key': k, 'group': st, 'spellings': [[f, n] for f, n in grp['forms'].items()],
                               'answer': {x: o[x] for x in ('type', 'latin', 'greek', 'description')} | {'distinct_names': False, 'main_forms': []},
                               'reused_from': 'judgments.jsonl'})
                continue
            top = sorted(grp['forms'].items(), key=lambda fn: (-fn[1], fn[0]))[:pr.MAX_FORMS]
            items.append({'key': k, 'group': st, 'forms': [[f, n] for f, n in top],
                          'snippets': collision_snippets(db, tx, eids[k], set(grp['forms']))})
    if reused:
        with open(out_path, 'a', encoding='utf-8') as f:
            for r in reused:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'{len(items)} group questions to ask, {len(reused)} taken from the earlier judgment', flush=True)

    def ask(client, it):
        spellings = [f for f, _c in it['forms']]
        txt = client.ask(pr.SYSTEM, pr.question(it['group'], it['forms'], it['snippets']), max_tokens=300)
        ans = pr.parse_judgment(txt, spellings)
        return {'key': it['key'], 'group': it['group'], 'spellings': it['forms'], 'answer': ans,
                'reply': txt if ans is None else None}

    run_pool(a, items, ask, out_path)


def step_greekfix(a):
    """Stage 4. Ask the model whether the Greek label of each old-flow split that has a spelling of the same key
    outside its main forms with the label's stem is the Greek name of the Latin name (entity_promote.greek_candidates).
    Reads --store (the base store) for the spellings and the lines."""
    j = load_judgments(a, greekfix=False)
    db, tx = ro(a.store), ro(os.path.join(a.passage_dir, 'window_texts.db'))
    eids = dict(db.execute("select name_key, eid from entities where source = 'names'"))
    cache = {}

    def spellings_of(key):
        if key not in cache:
            cache[key] = [f for (f,) in db.execute('select distinct form from mention_rows where eid = ?', (eids[key],))] if key in eids else []
        return cache[key]

    cands = pr.greek_candidates(j, spellings_of)
    out_path = p(a, 'greekfix_judgments.jsonl')
    done = {r['key'] for r in read_jsonl(out_path) if r.get('answer') is not None}
    items = []
    for k, same in sorted(cands.items()):
        if k in done:
            continue
        x = j[k]
        items.append({'key': k, 'latin': x['latin'], 'type': x['type'], 'description': x['description'], 'greek': x['greek'],
                      'same': same, 'snippets': collision_snippets(db, tx, eids[k], set(same), n=3, tag='greekfix')})
    print(f'{len(cands)} labels to check, {len(items)} to ask', flush=True)

    def ask(client, it):
        txt = client.ask(pr.GREEK_FIX_SYSTEM, pr.greek_fix_question(it['latin'], it['type'], it['description'], it['greek'], it['snippets']),
                         max_tokens=40)
        v = pr.parse_greek_fix(txt)
        return {'key': it['key'], 'latin': it['latin'], 'greek': it['greek'], 'spellings': it['same'][:6], 'answer': v,
                'reply': txt if v is None else None}

    run_pool(a, items, ask, out_path)


def load_collisions(a):
    """(candidates, answers) of the stem test from --work-dir, or ({}, {}) when the step was not run. A group
    answer whose label shares no five letters with the group's spellings is not used (the group stays with
    the corpus name)."""
    path = p(a, 'collide_candidates.json')
    if not os.path.exists(path):
        return {}, {}
    cand = json.load(open(path, encoding='utf-8'))
    answers = collections.defaultdict(dict)
    for r in read_jsonl(p(a, 'collide_judgments.jsonl')):
        ans = r.get('answer')
        if not ans:
            continue
        g = cand.get(r['key'], {}).get(r['group'])
        if g is None:
            continue
        probe = dict(ans, distinct_names=True, main_forms=list(g['forms']))
        answers[r['key']][r['group']] = None if pr.contradicts_label(probe) else ans
    return cand, dict(answers)


# ------------------------------------------------------------------ the description confirmation

def promoted_rows(db):
    return db.execute("select e.eid, e.entity_id, e.type, e.label, l.display_label_grc, l.description "
                      "from entities e join entity_labels l on l.eid = e.eid where e.source = 'promoted' "
                      "order by e.entity_id").fetchall()


def step_confirm(a):
    """Is each promoted entity's description right as five lines from five works use the name. A
    second question confirms each correction. Reads --out (the built stage 3a store)."""
    db, tx = ro(a.out), ro(os.path.join(a.passage_dir, 'window_texts.db'))
    rows = promoted_rows(db)
    p1 = p(a, 'confirm1.jsonl')
    # stage 4: an answer counts only for the description it was asked about (an entity that keeps its id can
    # get another description from a collision group)
    current = {ent: desc for eid, ent, typ, lat, grc, desc in rows}
    done = {r['id'] for r in read_jsonl(p1) if r.get('answer') is not None and r.get('original') == current.get(r['id'])}
    items = [{'id': ent, 'eid': eid, 'type': typ, 'latin': lat, 'greek': grc, 'description': desc}
             for eid, ent, typ, lat, grc, desc in rows if desc and ent not in done]
    print(f'{len(rows)} promoted entities, {len(items)} first questions to ask', flush=True)
    for it in items:
        it['snippets'] = pr.context_lines(db, tx, it['eid'], 5, 'confirm')

    def ask1(client, it):
        txt = client.ask(pr.CONFIRM_SYSTEM, pr.confirm_question(it['latin'], it['greek'], it['type'], it['description'], it['snippets']),
                         max_tokens=120)
        r = pr.parse_confirm(txt)
        return {'id': it['id'], 'original': it['description'], 'answer': None if r is None else ('yes' if r[0] else 'no'),
                'corrected': None if r is None else r[1], 'reply': txt if r is None else None}

    run_pool(a, items, ask1, p1, 120)
    first = {r['id']: r for r in read_jsonl(p1) if r.get('answer') is not None and r.get('original') == current.get(r['id'])}
    p2 = p(a, 'confirm2.jsonl')
    done2 = {r['id'] for r in read_jsonl(p2) if r.get('answer') is not None
             and r.get('corrected') == (first.get(r['id']) or {}).get('corrected')}
    rowmap = {ent: (eid, typ, lat, grc) for eid, ent, typ, lat, grc, _d in rows}
    items2 = []
    for ent, r in first.items():
        if r['answer'] == 'no' and r['corrected'] and ent not in done2 and ent in rowmap:
            eid, typ, lat, grc = rowmap[ent]
            items2.append({'id': ent, 'eid': eid, 'type': typ, 'latin': lat, 'greek': grc, 'description': r['corrected'],
                           'snippets': pr.context_lines(db, tx, eid, 5, 'confirm')})
    print(f'{len(items2)} second questions (corrections) to ask', flush=True)

    def ask2(client, it):
        txt = client.ask(pr.CONFIRM_SYSTEM, pr.confirm_question(it['latin'], it['greek'], it['type'], it['description'], it['snippets']),
                         max_tokens=120)
        r = pr.parse_confirm(txt)
        return {'id': it['id'], 'corrected': it['description'], 'answer': None if r is None else ('yes' if r[0] else 'no'),
                'again': None if r is None else r[1], 'reply': txt if r is None else None}

    run_pool(a, items2, ask2, p2, 120)


def step_describe(a):
    """Store the confirmed descriptions in --out and rebuild its catalog."""
    db = sqlite3.connect(a.out)
    rows = promoted_rows(db)
    current = {ent: desc for eid, ent, typ, lat, grc, desc in rows}
    first = {r['id']: r for r in read_jsonl(p(a, 'confirm1.jsonl'))
             if r.get('answer') is not None and r.get('original') == current.get(r['id'])}
    second = {r['id']: r for r in read_jsonl(p(a, 'confirm2.jsonl'))
              if r.get('answer') is not None and r.get('corrected') == (first.get(r['id']) or {}).get('corrected')}
    final, tally = {}, collections.Counter()
    for eid, ent, typ, lat, grc, desc in rows:
        f = first.get(ent)
        f = None if f is None else (f['answer'] == 'yes', f['corrected'] or '')
        s2 = second.get(ent)
        s2 = None if s2 is None else (s2['answer'] == 'yes', s2.get('again') or '')
        final[eid] = pr.final_description(desc, f, s2) if desc else ''
        tally['kept_confirmed' if f and f[0] and desc else 'corrected_confirmed' if f and not f[0] and final[eid]
              else 'emptied' if desc else 'no_description'] += 1
    pr.apply_descriptions(db, final)
    db.execute("delete from meta where key = 'description_pass'")
    db.execute("insert into meta values ('description_pass', ?)", (json.dumps(dict(tally)),))
    db.commit()
    db.close()
    extras.write_catalog(a.out)
    print(json.dumps(dict(tally)))
    json.dump(dict(tally), open(p(a, 'description_tally.json'), 'w'))


# ------------------------------------------------------------------ judgments

def load_judgments(a, fixes=True, labelfix=True, greekfix=True):
    """{key: judgment}: the last usable answer for each key, with the split fix applied, then (stage 3b)
    the label fix of the splits that still contradict their label."""
    out = {}
    for r in read_jsonl(p(a, 'judgments.jsonl')):
        if r.get('answer'):
            out[r['key']] = r['answer']
    if fixes:
        fx = {r['key']: r['answer'] for r in read_jsonl(p(a, 'judgments_splitfix.jsonl')) if r.get('answer')}
        a.split_fixed = pr.apply_split_fix(out, fx)
        if labelfix:
            lf = {r['key']: (r['answer']['latin'], r['answer']['greek']) for r in read_jsonl(p(a, 'judgments_labelfix.jsonl'))
                  if r.get('answer')}
            a.label_fixed = pr.apply_label_fix(out, lf)
    cand, answers = load_collisions(a)
    if cand and fixes:
        out, rep = pr.collision_judgments(out, cand, answers)
        a.collision_report = rep
    if greekfix and fixes and getattr(a, 'apply_greekfix', False):
        gx = {r['key']: r['answer'] for r in read_jsonl(p(a, 'greekfix_judgments.jsonl')) if r.get('answer')}
        a.greek_fixed = pr.apply_greek_fix(out, gx)
    return out


def step_stats(a):
    j = load_judgments(a)
    c = collections.Counter(x['type'] for x in j.values())
    splits = sum(1 for x in j.values() if x['distinct_names'])
    print(json.dumps({'judged': len(j), 'by_type': dict(c), 'split_groups': splits,
                      'with_greek': sum(1 for x in j.values() if x['greek'])}, indent=1))


# ------------------------------------------------------------------ build

def step_build(a):
    t0 = time.time()
    if os.path.exists(a.out):
        os.remove(a.out)
    shutil.copyfile(a.store, a.out)
    db = sqlite3.connect(a.out)
    changed = pr.write_display_labels(db)
    judgments = load_judgments(a)
    rep = pr.promote_store(db, judgments, greek_stems=pr.greek_stems_of_store(db))
    full = getattr(a, 'collision_report', {})
    rep['collisions'] = {k: v for k, v in full.items() if k != 'keys'}
    json.dump(full, open(p(a, 'collision_report.json'), 'w'), ensure_ascii=False, indent=1)
    rep['greek_label_removed_by_the_model'] = getattr(a, 'greek_fixed', 0)
    rep['split_fixed'] = getattr(a, 'split_fixed', 0)
    rep['label_fixed'] = getattr(a, 'label_fixed', 0)
    dd = pr.dedupe_promoted(db)
    rep['duplicates'] = {k: v for k, v in dd.items() if k != 'examples'}
    rep['duplicate_examples'] = dd['examples']
    db.execute("delete from meta where key in ('promotion', 'promotion_seconds')")
    db.execute("insert into meta values ('promotion', ?)", (json.dumps({k: v for k, v in rep.items() if not k.endswith('examples')}),))
    db.commit()
    db.close()
    extras.write_catalog(a.out)
    db = sqlite3.connect(a.out)
    db.execute("insert into meta values ('promotion_seconds', ?)", (str(round(time.time() - t0)),))
    db.commit()
    db.close()
    json.dump(rep, open(p(a, 'promotion_report.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump([[e, o, n] for e, o, n in changed], open(p(a, 'label_changes.json'), 'w'), ensure_ascii=False)
    print(json.dumps({k: v for k, v in rep.items() if not k.endswith('examples')}), f'seconds {time.time() - t0:.0f}')


# ------------------------------------------------------------------ draw

def step_draw(a):
    db = ro(a.out)
    rows = db.execute("select e.eid, e.entity_id, e.type, e.label, l.display_label_grc, l.description "
                      "from entities e left join entity_labels l on l.eid = e.eid where e.source = 'promoted' "
                      "order by e.entity_id").fetchall()
    rnd = random.Random(a.seed)
    pick = rnd.sample(rows, min(40, len(rows)))
    out = []
    for eid, ent, typ, label, grc, desc in pick:
        forms = db.execute('select form, count(*) c from mention_rows where eid = ? group by form order by c desc limit 8',
                           (eid,)).fetchall()
        out.append({'id': ent, 'type': typ, 'latin': label, 'greek': grc, 'description': desc,
                    'forms': [f for f, _c in forms]})
    json.dump(out, open(p(a, 'promoted40_drawn.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'{len(out)} drawn from {len(rows)} promoted, seed {a.seed}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', choices=['prepare', 'ask', 'splitfix', 'labelfix', 'collide', 'greekfix', 'build', 'confirm', 'describe', 'draw', 'stats'])
    ap.add_argument('--store', help='the stage 2b store (read only)')
    ap.add_argument('--out', help='the stage 3a store to write (build) or read (draw)')
    ap.add_argument('--passage-dir', default=os.path.join(ROOT, 'data', 'passage_index'))
    ap.add_argument('--work-dir', required=True)
    ap.add_argument('--threads', type=int, default=48)
    ap.add_argument('--budget', type=int, default=480, help='seconds the ask step may run')
    ap.add_argument('--seed', type=int, default=20261021)
    ap.add_argument('--apply-greekfix', action='store_true',
                    help='build: remove the Greek labels the model called a different name (greekfix step). Off by default.')
    a = ap.parse_args()
    os.makedirs(a.work_dir, exist_ok=True)
    globals()['step_' + a.step](a)
    return 0


if __name__ == '__main__':
    sys.exit(main())
