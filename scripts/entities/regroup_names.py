"""Take wrongly grouped spellings out of their People & Places entries (see backend/entity_regroup.py).

    python scripts/entities/regroup_names.py STORE_COPY [--audit-only]
    python scripts/entities/regroup_names.py STORE_COPY --calibrate | --judge | --apply | --sample

Works on the copy it is given, never on the production store. The model steps read the gateway address and
key with the same function the event scripts use and never print them.
"""
import argparse
import importlib.util
import json
import os
import random
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, ROOT)

from backend import entity_regroup as rg  # noqa: E402

WORK = os.path.expanduser('~/tesserae-backups/regroup_2026-10-21')
WINDOWS = '/var/www/tesseraev6_flask/data/passage_index/window_texts.db'
PROGRESS = os.path.join(WORK, 'PROGRESS.txt')


def log(msg):
    line = f'{time.strftime("%H:%M")} {msg}'
    print(line, flush=True)
    with open(PROGRESS, 'a') as f:
        f.write(line + '\n')


def gateway():
    spec = importlib.util.spec_from_file_location('jsr', os.path.join(ROOT, 'scripts/events/judge_scholarship_relevance.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m._env()


def workers():
    busy = subprocess.run(['pgrep', '-f', r'^\S*python\S* scripts/events/add_theme_passages\.py'], capture_output=True, text=True).stdout.split()
    return 4 if busy else 8


def judge_groups(db, groups, cache_path, lines, nworkers=None, label=''):
    """groups: [(eid, entity_id, stem, forms {spelling: rows})]. Asks every group not yet in the cache, stores the
    answers, returns {(entity_id, stem): answer}."""
    cache = rg.open_cache(cache_path)
    have = {(a, b): c for a, b, c in cache.execute('select entity_id, stem, answer from answers where version = ?',
                                                   (rg.PROMPT_VERSION,))}
    todo = [g for g in groups if (g[1], g[2]) not in have]
    url, key = gateway()
    stats = {}
    t0 = time.time()
    done = [0]

    def one(item):
        g, prompt = item
        reply = rg.ask(url, key, prompt, stats)
        ans, _ = rg.parse_answer(reply)
        return g, ans or 'NONE', reply

    n = nworkers or workers()
    with ThreadPoolExecutor(n) as pool:
        for i in range(0, len(todo), 400):
            batch = []
            for g in todo[i:i + 400]:
                eid, entity_id, stem, forms = g
                heading, desc = rg.entity_card(db, eid)
                batch.append((g, rg.question(heading, desc, forms, rg.example_lines(db, lines, eid, list(forms)))))
            for g, ans, reply in pool.map(one, batch):
                cache.execute('insert or replace into answers values (?,?,?,?,?,?)',
                              (g[1], g[2], rg.PROMPT_VERSION, ans, reply, json.dumps(g[3], ensure_ascii=False)))
                have[(g[1], g[2])] = ans
                done[0] += 1
            cache.commit()
            if todo and (done[0] % 400 == 0 or done[0] == len(todo)):
                rate = done[0] / (time.time() - t0)
                log(f'{label} judged {done[0]}/{len(todo)} new, {rate:.2f}/s, workers {n}, errors {stats.get("errors", 0)}')
    return have


# (entity id, spelling, expected): the ten wrong and the right ones the project lead named on 2026-10-21
CALIBRATION = [
    ('pn:ekata', 'Ἑκαταῖος', 'DIFFERENT'), ('nm:khlod', 'Chlodovechi', 'DIFFERENT'), ('nm:khlod', 'Chloduici', 'DIFFERENT'),
    ('nm:leuko', 'Leuconoe', 'DIFFERENT'), ('nm:flori', 'Florizel', 'DIFFERENT'), ('nm:beren', 'Berengarii', 'DIFFERENT'),
    ('pn:silan', 'Silanion', 'DIFFERENT'), ('nm:filom', 'Filometore', 'DIFFERENT'), ('nm:metro', 'Μητροβίου', 'DIFFERENT'),
    ('pn:kelti', 'Κελτική', 'DIFFERENT'), ('pn:filog', 'Philogeus', 'DIFFERENT'),
    ('ln:E0364', 'Venerem', 'SAME'), ('ln:E0364', 'Ἀφροδίτης', 'SAME'), ('ln:E0091', 'Αἰνείας', 'SAME'),
    ('ln:E0091', 'Aenean', 'SAME'), ('pl:462086', 'Ἀκράγαντα', 'SAME'), ('nm:kerer', 'Cereremque', 'SAME'),
    ('nm:tlepo:main', 'Tlepolemumque', 'SAME'), ('ln:E0670', 'Ἰθάκην', 'SAME'), ('nm:krema', 'Κρεμαϲτή', 'SAME'),
]


def group_of(db, entity_id, form):
    """(eid, stem, {spelling: rows}) of the stem group of `form` among the mention rows of the entity."""
    eid = db.execute('select eid from entities where entity_id = ?', (entity_id,)).fetchone()[0]
    st = rg.stem_of(form)
    forms = {f: n for f, n in db.execute('select form, count(*) from mention_rows where eid = ? group by form', (eid,))
             if rg.stem_of(f) == st}
    return eid, st, forms


def calibrate(db, cache_path):
    lines = rg.Lines(WINDOWS)
    groups = []
    for entity_id, form, _want in CALIBRATION:
        eid, st, forms = group_of(db, entity_id, form)
        groups.append((eid, entity_id, st, forms))
    got = judge_groups(db, groups, cache_path, lines, label='calibration')
    bad = 0
    for (entity_id, form, want), g in zip(CALIBRATION, groups):
        ans = got[(entity_id, g[2])]
        ok = ans == want if want == 'DIFFERENT' else ans != 'DIFFERENT'
        bad += not ok
        log(f'calibration {entity_id} {form}: want {want}, got {ans} {"ok" if ok else "MISS"}')
    return bad


def run_judge(db, a):
    """Layer 2 over every candidate group, the largest first, until done or --max-seconds passes. The cache is
    kept, so a later call goes on where this one stopped."""
    saved = os.path.join(WORK, 'layer1_groups.json')
    if os.path.exists(saved) and a.store.endswith('entities_orig.sqlite'):
        rep = {'groups': json.load(open(saved))}       # the layer 1 groups of the original copy, written by --audit-only --out
    else:
        rep = rg.audit(db)
    ent = dict(db.execute('select eid, entity_id from entities'))
    groups = sorted(((g[0], ent[g[0]], g[1], g[2], g[3]) for g in rep['groups']), key=lambda g: -g[4])
    cache_path = os.path.join(WORK, 'answers.sqlite')
    cache = rg.open_cache(cache_path)
    have = {(x, y) for x, y in cache.execute('select entity_id, stem from answers where version = ?', (rg.PROMPT_VERSION,))}
    cache.close()
    todo = [g[:4] for g in groups if (g[1], g[2]) not in have]
    log(f'judge: {len(groups)} groups, {len(have)} cached, {len(todo)} to ask')
    lines = rg.Lines(WINDOWS)
    t0 = time.time()
    last = [0]
    step = 100
    for i in range(0, len(todo), step):
        if a.max_seconds and time.time() - t0 > a.max_seconds:
            break
        got = judge_groups(db, todo[i:i + step], cache_path, lines, nworkers=a.workers or None, label='judge')
        covered = sum(g[4] for g in groups if (g[1], g[2]) in got or (g[1], g[2]) in have)
        total = sum(g[4] for g in groups)
        if time.time() - last[0] > 1200 or i + step >= len(todo):
            last[0] = time.time()
            log(f'COVERAGE: judged groups hold {covered} of {total} candidate rows ({100 * covered / total:.1f} percent)')
    return None


SAMPLE = os.path.join(WORK, 'sample300.json')


def run_sample(db, when, a):
    """300 (entity, spelling) pairs drawn once, weighted by mention rows, from the ORIGINAL store (before). The
    share the model calls DIFFERENT is measured on them before and, for the same spellings wherever they are
    now, after the run."""
    lines = rg.Lines(WINDOWS)
    path = os.path.join(WORK, f'sample_answers_{when}.sqlite')
    if when == 'before':
        rows = db.execute('select e.entity_id, m.form, count(*) from mention_rows m join entities e using(eid) '
                          'group by m.eid, m.form').fetchall()
        rows = [r for r in rows if not rg.protected(r[0])]
        rnd = random.Random(20261021)
        pairs = rnd.choices(rows, weights=[r[2] for r in rows], k=300)
        pairs = list(dict.fromkeys((r[0], r[1]) for r in pairs))
        while len(pairs) < 300:
            r = rnd.choices(rows, weights=[r[2] for r in rows])[0]
            if (r[0], r[1]) not in pairs:
                pairs.append((r[0], r[1]))
        json.dump(pairs, open(SAMPLE, 'w'), ensure_ascii=False)
    pairs = json.load(open(SAMPLE))
    groups = []
    best = {}
    if when == 'after':
        want = {f for _e, f in pairs}
        for form, eid, n in db.execute('select form, eid, count(*) from mention_rows group by form, eid'):
            if form in want and (form not in best or n > best[form][1]):
                best[form] = (eid, n)
    for entity_id, form in pairs:
        if when == 'before':
            eid = db.execute('select eid from entities where entity_id = ?', (entity_id,)).fetchone()[0]
        else:       # the entity that holds most rows of this spelling now
            eid = best[form][0]
            entity_id = db.execute('select entity_id from entities where eid = ?', (eid,)).fetchone()[0]
        n = db.execute('select count(*) from mention_rows where eid = ? and form = ?', (eid, form)).fetchone()[0]
        groups.append((eid, entity_id, 'S:' + form, {form: n}))
    got = judge_groups(db, groups, path, lines, label='sample-' + when)
    c = {}
    for g in groups:
        c[got[(g[1], g[2])]] = c.get(got[(g[1], g[2])], 0) + 1
    log(f'SAMPLE {when}: {c} DIFFERENT share {c.get("DIFFERENT", 0) / len(groups):.3f} of {len(groups)}')
    if when == 'after':       # the pairs the run moved or carved, and the rest
        changed = [g for g, p in zip(groups, pairs) if g[1] != p[0]]
        d = sum(1 for g in changed if got[(g[1], g[2])] == 'DIFFERENT')
        log(f'SAMPLE after, pairs the run moved or carved: {len(changed)} of {len(groups)}, still DIFFERENT {d}')


def differences(cache_path):
    cache = rg.open_cache(cache_path)
    out = [(a, b, json.loads(f)) for a, b, f in cache.execute(
        "select entity_id, stem, forms from answers where version = ? and answer = 'DIFFERENT' and stem not like 'S:%'",
        (rg.PROMPT_VERSION,))]
    return out


def recheck(db, diffs):
    """The groups the model called DIFFERENT, minus the spellings the layer 1 of today accepts (the rule for
    headings in -as was added after the judging: Aenean, \u1f08\u03ba\u03c1\u03ac\u03b3\u03b1\u03bd\u03c4\u03b1). A group left with
    no spelling is dropped."""
    ids = dict(db.execute('select entity_id, eid from entities'))
    pairs = {}
    out = []
    dropped = 0
    for entity_id, stem, forms in diffs:
        eid = ids.get(entity_id)
        if eid is None:
            continue
        if eid not in pairs:
            full = dict(db.execute('select form, count(*) from mention_rows where eid = ? group by form', (eid,)))
            pairs[eid] = rg.layer1(db, eid, full)[1]
        keep = {f: n for f, n in forms.items() if f in pairs[eid]}
        dropped += len(forms) - len(keep)
        if keep:
            out.append((entity_id, stem, keep))
    log(f'recheck: {len(diffs)} DIFFERENT groups, {dropped} spellings accepted by the layer 1 of the final rules, {len(out)} groups left')
    return out


def run_apply(db, a):
    from backend import entity_extras as ex
    diffs = recheck(db, differences(os.path.join(WORK, 'answers.sqlite')))
    before = db.execute('select count(*) from mention_rows').fetchone()[0]
    ents_before = db.execute('select count(*) from entities').fetchone()[0]
    rep = rg.apply_differences(db, diffs, log=log)
    db.commit()
    after = db.execute('select count(*) from mention_rows').fetchone()[0]
    rep.update({'differences': len(diffs), 'mention_rows_before': before, 'mention_rows_after': after,
                'entities_before': ents_before,
                'entities_after': db.execute('select count(*) from entities').fetchone()[0]})
    ex.add_form_search_names(db, log=log)
    db.commit()
    db.close()
    ex.write_catalog(a.store, log=log)
    ex.write_form_index(a.store, log=log)
    db = sqlite3.connect(a.store)
    rep['integrity'] = db.execute('pragma integrity_check').fetchone()[0]
    json.dump(rep, open(os.path.join(WORK, 'apply_report.json'), 'w'), ensure_ascii=False, indent=1)
    log('APPLY ' + json.dumps({k: v for k, v in rep.items() if k not in ('moves', 'carves')}))


def run_sheet(db, a):
    """sample_60.md: 30 pairs from moved or carved groups and 30 from kept candidate groups, with one line each."""
    lines = rg.Lines(WINDOWS)
    rep = json.load(open(os.path.join(WORK, 'apply_report.json')))
    rnd = random.Random(7)
    orig = sqlite3.connect(os.path.join(WORK, 'entities_orig.sqlite'))
    moved = rnd.sample(rep['moves'] + rep['carves'], 30)
    cache = rg.open_cache(os.path.join(WORK, 'answers.sqlite'))
    kept = cache.execute("select entity_id, stem, forms, answer from answers where version = ? and answer != 'DIFFERENT' "
                         "and stem not like 'S:%'", (rg.PROMPT_VERSION,)).fetchall()
    kept = rnd.sample(kept, 30)
    out = ['# 60 spellings the regroup judged, for reading', '',
           'Thirty were taken out of their entry (moved to another entry or made into a new name) and thirty were '
           'kept where they were. Each shows the entry heading, the spelling and one line of text. Mark the ones '
           'that are wrong.', '']

    def one(i, kind, entity_id, form, where):
        r = orig.execute('select eid, label from entities where entity_id = ?', (entity_id,)).fetchone()
        ex = rg.example_lines(orig, lines, r[0], [form], n=1)
        out.append(f'{i}. {kind}. Entry: {r[1]} ({entity_id}). Spelling: {form}. {where}')
        line = ex[0] if ex else '(no line found)'
        i = line.find('\u27e6')
        if len(line) > 420 and i >= 0:
            line = '...' + line[max(0, i - 200):i + 220] + '...'
        out.append(f'   Line: {line}')
        out.append('')

    for i, (entity_id, to, fs, n) in enumerate(moved, 1):
        one(i, 'Taken out', entity_id, fs[0], f'Now in: {to}.')
    for j, (entity_id, stem, forms, ans) in enumerate(kept, 31):
        one(j, 'Kept', entity_id, sorted(json.loads(forms))[0], f'Model answer: {ans}.')
    open(os.path.join(WORK, 'sample_60.md'), 'w').write('\n'.join(out))
    log('sheet written')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('store')
    ap.add_argument('--audit-only', action='store_true')
    ap.add_argument('--out', default=None)
    ap.add_argument('--calibrate', action='store_true')
    ap.add_argument('--judge', action='store_true')
    ap.add_argument('--sample', choices=('before', 'after'))
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--sheet', action='store_true')
    ap.add_argument('--max-seconds', type=int, default=0)
    ap.add_argument('--workers', type=int, default=0)
    a = ap.parse_args()
    db = sqlite3.connect(a.store)
    if a.calibrate:
        sys.exit(1 if calibrate(db, os.path.join(WORK, 'answers.sqlite')) else 0)
    if a.judge:
        return run_judge(db, a)
    if a.sample:
        return run_sample(db, a.sample, a)
    if a.apply:
        return run_apply(db, a)
    if a.sheet:
        return run_sheet(db, a)
    rep = rg.audit(db)
    print(json.dumps(rep['summary'], indent=1, ensure_ascii=False))
    if a.out:
        json.dump(rep['groups'], open(a.out, 'w'), ensure_ascii=False)


if __name__ == '__main__':
    main()
