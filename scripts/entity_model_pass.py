"""Stage 1d: a model pass on the entity lemma sets and on the windows that name one of several
entities (2026-10-17). Every step reads and writes files in --work-dir, so a step that is cut
off by a time budget picks up where it stopped.

    venv/bin/python scripts/entity_model_pass.py STEP --entities-json KEYS.json \
        --passage-dir data/passage_index --audit-csv lemma_set_audit.csv \
        --graded-dir research/entities --work-dir research/entities/stage1d_work

STEP, in order:
    prepare   type counts, lemmas, the pass-one questions            (tess-job, about 5 minutes)
    pass1     ask the gateway about every (entity, lemma) pair         (--budget SECONDS, resumable)
    plan2     apply pass one, find the windows with an ambiguous name, write the pass-two questions
    pass2     ask the gateway which candidate each window names        (--budget SECONDS, resumable)
    eval      the fixed graded pairs before and after each pass
    build     write the store with both passes applied (--out)
    draw      draw the fresh pairs from that store (--seed)

The gateway address and key are read by backend/entity_gateway.py from the production .env and
are never printed or written. The judgments, prompts and graded files stay in --work-dir, which is
private; this script carries no data.
"""
import argparse
import collections
import csv
import json
import os
import pickle
import random
import re
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend import entity_gateway as gw  # noqa: E402
from backend import entity_index as ei  # noqa: E402
from backend import entity_lemma as el  # noqa: E402
from backend import entity_model_pass as mp  # noqa: E402

GRADED = ['precision_60', 'precision_scope40_regraded', 'precision_holdout40', 'precision_lemma_holdout40']
EXTRA_EXCLUDE = ['precision_1c_holdout40']
SNIPPETS = 3
SEED_SNIPPETS = 20261017


def load_world(a):
    keys = json.load(open(a.entities_json, encoding='utf-8'))
    entities, _ = ei.merge_list_entities(keys)
    return keys, entities


def p(a, name):
    return os.path.join(a.work_dir, name)


def read_jsonl(path):
    out = []
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            if line.strip():
                out.append(json.loads(line))
    return out


def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def load_state(a):
    st = pickle.load(open(p(a, 'state.pkl'), 'rb'))
    return st['types'], st['prep']


def open_texts(a):
    return sqlite3.connect(f"file:{os.path.join(a.passage_dir, 'window_texts.db')}?mode=ro", uri=True)


# ------------------------------------------------------------------ judgments

def load_decisions(path):
    """{(lang, entity_id, lemma): 'drop'|'keep'|'other'} from the pass-one judgments (the last
    answer for a pair wins, a missing answer leaves the pair to the audit)."""
    last = {}
    for r in read_jsonl(path):
        last[(r['lang'], r['entity_id'], r['lemma'])] = r.get('answer')
    mapping = {'yes': 'keep', 'demonym': 'drop', 'common': 'drop', 'other': 'other'}
    return {k: mapping[v] for k, v in last.items() if v in mapping}


def load_answers(path, rev_path=None):
    """{(window id, candidate entity ids): chosen entity id or None} from the pass-two judgments.
    With rev_path (the same questions asked with the candidates in reverse order), a window with
    two or more candidates is answered only when both orders name the same entity or both say
    none. When the two orders differ the window stays unanswered and keeps all its candidates."""
    fwd = {}
    for r in read_jsonl(path):
        if r.get('answer') is not None:
            fwd[(r['window_id'], tuple(r['cands']))] = r['chosen']
    if not rev_path:
        return fwd
    rev = {}
    for r in read_jsonl(rev_path):
        if r.get('answer') is not None:
            rev[(r['window_id'], tuple(sorted(r['cands'])))] = r['chosen']
    out = {}
    for key, chosen in fwd.items():
        if len(key[1]) < 2:
            out[key] = chosen
        elif (key[0], tuple(sorted(key[1]))) in rev and rev[(key[0], tuple(sorted(key[1])))] == chosen:
            out[key] = chosen
    return out


# ------------------------------------------------------------------ gateway runs

def run_stage(a, jobs, ask, record, out_path, key_of, plan):
    """Run `ask(job) -> record dict` for the jobs without a usable answer, in the segments of
    `plan` ([(count, threads), ...] and then the best rate seen). Stops after --budget seconds."""
    done = {}
    for r in read_jsonl(out_path):
        done[key_of(r)] = r
    todo = [j for j in jobs if (done.get(key_of(j)) or {}).get('answer') is None]
    print(f'{len(jobs)} questions, {len(jobs) - len(todo)} answered, {len(todo)} to ask', flush=True)
    rates = []
    rate_path = out_path + '.rates.json'
    if os.path.exists(rate_path):
        rates = json.load(open(rate_path))
    t_start = time.time()
    pos = 0
    seg = 0
    already = len(jobs) - len(todo)
    best = a.threads
    plan = list(plan)
    skipped = already
    f = open(out_path, 'a', encoding='utf-8')
    try:
        while pos < len(todo) and time.time() - t_start < a.budget:
            if seg < len(plan):
                count, threads = plan[seg]
                if skipped >= count:
                    skipped -= count
                    seg += 1
                    continue
                count -= skipped
                skipped = 0
            else:
                good = [r for r in rates if r['stage'] == os.path.basename(out_path) and r['seconds'] > 5 and r['n'] >= 100]
                best = max(good, key=lambda r: r['rps'])['threads'] if good else a.threads
                if a.fixed_threads:
                    best = a.fixed_threads
                count, threads = (a.probe_jobs or 1000), best
            chunk = todo[pos:pos + count]
            seg += 1
            # a long segment is cut into pieces so the budget is checked
            t0 = time.time()
            n_ok = n_bad = 0
            i = 0
            while i < len(chunk) and time.time() - t_start < a.budget:
                piece = chunk[i:i + max(threads * 6, 60)]
                results, _secs = gw.run_jobs(piece, ask, threads)
                for r in results:
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
                    n_ok += r.get('answer') is not None
                    n_bad += r.get('answer') is None
                f.flush()
                i += len(piece)
            secs = time.time() - t0
            pos += i
            if i:
                rec = {'stage': os.path.basename(out_path), 'threads': threads, 'n': i, 'seconds': round(secs, 1),
                       'rps': round(i / max(secs, 1e-9), 2), 'no_answer': n_bad}
                rates.append(rec)
                print(json.dumps(rec), flush=True)
                json.dump(rates, open(rate_path, 'w'))
    finally:
        f.close()
    left = len(todo) - pos
    print(f'asked {pos} this run, {left} still to ask, gateway {json.dumps(client_stats)}', flush=True)


client_stats = {}


def make_client():
    url, key = gw.load_config()
    return gw.Gateway(url, key)


# ------------------------------------------------------------------ prepare

def step_prepare(a):
    t0 = time.time()
    keys, entities = load_world(a)
    ids = json.load(open(os.path.join(a.passage_dir, 'ids.json')))
    unit = ei.unit_windows(ids)
    del ids
    texts = open_texts(a)
    types = el.count_types(texts, unit)
    resolver = el.Resolver()
    prep = el.prepare_lemmas(entities, types, resolver)
    prep['stats'] = {l: dict(v) for l, v in prep['stats'].items()}
    print(f'prepared {time.time() - t0:.0f}s', flush=True)
    pickle.dump({'types': types, 'prep': prep}, open(p(a, 'state.pkl'), 'wb'), protocol=4)

    t2e, info = el.assemble_matcher(entities, types, prep, log=lambda *_: None)
    by_id = {e['entity_id']: i for i, e in enumerate(entities)}
    pairs = set()
    for r in csv.DictReader(open(a.audit_csv, encoding='utf-8')):
        pairs.add((r['language'], by_id[r['entity_id']], r['lemma']))
    n_file = len(pairs)
    for (lang, idx, lem), (action, why) in info['proposals'].items():
        if action != 'keep':
            pairs.add((lang, idx, lem))
    print(f'{n_file} rows in the audit file, {len(pairs)} with every review and drop row', flush=True)

    # forms and example lines: one pass over the windows
    type_lemma = info['type_lemma']
    wanted = {l: {} for l in ei.LANGS}
    for lang, idx, lem in pairs:
        wanted[lang][lem] = True
    wf = {l: {f for f, lem in type_lemma[l].items() if lem in wanted[l]} for l in ei.LANGS}
    rnd = random.Random(SEED_SNIPPETS)
    seen = collections.Counter()
    res = collections.defaultdict(list)
    forms = collections.defaultdict(collections.Counter)
    for wid, lang, text in texts.execute('select id, language, text from window_texts'):
        if wid not in unit or lang not in wf:
            continue
        wset = wf[lang]
        for raw, f, initial in el.tokens_of(text):
            if f not in wset or initial or not el.is_cap(raw):
                continue
            key = (lang, type_lemma[lang][f])
            forms[key][raw] += 1
            seen[key] += 1
            if len(res[key]) < SNIPPETS:
                res[key].append(mp.line_snippet(text, raw))
            else:
                j = rnd.randrange(seen[key])
                if j < SNIPPETS:
                    res[key][j] = mp.line_snippet(text, raw)
    print(f'snippets collected {time.time() - t0:.0f}s', flush=True)
    jobs = []
    for lang, idx, lem in sorted(pairs, key=lambda x: (entities[x[1]]['entity_id'], x[0], x[2])):
        e = entities[idx]
        fs = [w for w, _ in forms[(lang, lem)].most_common(3)]
        user = mp.pass1_prompt(e, lem, lang, fs, res[(lang, lem)])
        jobs.append({'entity_id': e['entity_id'], 'lang': lang, 'lemma': lem, 'prompt': user,
                     'audit_action': info['proposals'][(lang, idx, lem)][0],
                     'audit_reason': info['proposals'][(lang, idx, lem)][1]})
    write_jsonl(p(a, 'pass1_jobs.jsonl'), jobs)
    print(f'{len(jobs)} pass-one questions written, {time.time() - t0:.0f}s', flush=True)


# ------------------------------------------------------------------ pass one

def step_pass1(a):
    global client_stats
    jobs = read_jsonl(p(a, 'pass1_jobs.jsonl'))
    cl = make_client()
    client_stats = cl.stats

    def ask(job):
        txt = cl.ask(mp.PASS1_SYSTEM, job['prompt'])
        return {'entity_id': job['entity_id'], 'lang': job['lang'], 'lemma': job['lemma'], 'answer': mp.parse_pass1(txt)}

    run_stage(a, jobs, ask, None, p(a, 'stage1d_lemma_judgments.jsonl'),
              lambda r: (r['lang'], r['entity_id'], r['lemma']), [(200, 8), (200, 16)])
    json.dump(cl.stats, open(p(a, 'pass1_gateway_%d.json' % int(time.time())), 'w'))


# ------------------------------------------------------------------ plan pass two

def _place_blurb(rows, label):
    """One line for a place from its Pleiades records: the record whose title is closest to
    the entity's label (a merged entity can carry five unrelated records), its first
    sentence when that is more than the generic 'An ancient place, cited: ...', and its
    coordinates."""
    lab = {w for w in ei.fold(label.replace('/', ' ')).split() if len(w) > 2}
    best, score = None, (-1, -1)
    for r in rows:
        title = {w for w in ei.fold(r['title'].replace('/', ' ')).split() if len(w) > 2}
        sc = (len(title & lab), len(r['description'] or ''))
        if sc > score:
            best, score = r, sc
    if best is None:
        return ''
    sent = mp.first_sentence(best['description'])
    bits = []
    if sent and not sent.startswith('An ancient place, cited'):
        bits.append(sent)
    try:
        lat, lon = float(best['representative_latitude']), float(best['representative_longitude'])
        bits.append('Pleiades %s, at %.1f%s %.1f%s.' % (best['title'], abs(lat), 'N' if lat >= 0 else 'S',
                                                       abs(lon), 'E' if lon >= 0 else 'W'))
    except (TypeError, ValueError):
        bits.append('Pleiades %s.' % best['title'])
    return ' '.join(bits)


def describe_candidates(a, entities, idxs):
    want = {pid for i in idxs for pid in entities[i]['pleiades'] if entities[i]['type'] == 'place'}
    recs = {}
    if want and os.path.exists(a.pleiades_places):
        with open(a.pleiades_places, encoding='utf-8-sig', newline='') as fh:
            for r in csv.DictReader(fh):
                if r['id'] in want:
                    recs[r['id']] = r
    store = ei.open_store(a.store)
    out = {}
    for i in idxs:
        e = entities[i]
        rows = store.execute(
            "select w.work, count(*) c from mention_rows m join windows w on w.wid=m.wid join entities x on x.eid=m.eid "
            "where x.entity_id=? group by w.work", (e['entity_id'],)).fetchall()
        by = collections.Counter()
        for w, c in rows:
            by[mp.author_of(w)] += c
        top = ', '.join(x for x, _ in by.most_common(3))
        bits = []
        if e['type'] == 'place':
            blurb = _place_blurb([recs[x] for x in e['pleiades'] if x in recs], e['label'])
            if blurb:
                bits.append(blurb)
        forms = sorted({k['greek'] for k in e['keys'] if k['greek']} | {x for k in e['keys'] for x in k['latin']})
        bits.append('Also written ' + ', '.join(forms[:4]) + '.')
        if top:
            bits.append('Named most in ' + top + '.')
        out[i] = {'label': e['label'], 'type': e['type'], 'description': ' '.join(bits)}
    return out


def step_plan2(a):
    t0 = time.time()
    keys, entities = load_world(a)
    types, prep = load_state(a)
    decisions = load_decisions(p(a, 'stage1d_lemma_judgments.jsonl'))
    t2e, info = el.assemble_matcher(entities, types, prep, decisions=decisions, log=lambda *_: None)
    texts = open_texts(a)
    ids = json.load(open(os.path.join(a.passage_dir, 'ids.json')))
    unit = ei.unit_windows(ids)
    del ids
    collect = {}
    rows, wmeta, tally = el.scan_windows_lemma(texts, unit, t2e, amb_tokens=info['amb_tokens'], collect=collect)
    by_lang = collections.Counter(r['lang'] for r in rows)
    print('pass-one table: mentions', len(rows), dict(by_lang), 'diag', json.dumps(info['diag']), flush=True)
    idxs = sorted({i for (_w, es) in collect for i in es})
    desc = describe_candidates(a, entities, idxs)
    jobs = []
    mentions_asked = 0
    for (wid, es), (raw, lang, text) in sorted(collect.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        cands = [desc[i] for i in es]
        f = ei._fold_tok(raw)
        jobs.append({'window_id': wid, 'lemma': info['type_lemma'][lang].get(f, f), 'lang': lang,
                     'cands': [entities[i]['entity_id'] for i in es], 'raw': raw,
                     'prompt': mp.pass2_prompt(mp.clip_words(text, raw), raw, cands)})
        mentions_asked += len(es)
    write_jsonl(p(a, 'pass2_jobs.jsonl'), jobs)
    summ = {'questions': len(jobs), 'mentions_covered_upper_bound': mentions_asked,
            'questions_by_language': dict(collections.Counter(j['lang'] for j in jobs)),
            'candidates_per_question': dict(collections.Counter(len(j['cands']) for j in jobs)),
            'pass_one_table_mentions': len(rows), 'pass_one_table_by_language': dict(by_lang),
            'windows_with_list_mention': len({r['wid'] for r in rows}),
            'homonym_flagged_mentions': sum(1 for r in rows if r['homonym']),
            'seconds': round(time.time() - t0)}
    json.dump(summ, open(p(a, 'plan2_summary.json'), 'w'), indent=1)
    print(json.dumps(summ, indent=1), flush=True)


# ------------------------------------------------------------------ pass two

def reverse_job(job):
    """The same question with the candidates listed in the opposite order."""
    m = re.search(r'Candidates:\n(.*?)\n0\. none of these', job['prompt'], re.S)
    lines = [re.sub(r'^\d+\. ', '', x) for x in m.group(1).split('\n')]
    lines.reverse()
    body = '\n'.join(f'{i}. {x}' for i, x in enumerate(lines, 1))
    prompt = job['prompt'][:m.start(1)] + body + job['prompt'][m.end(1):]
    return dict(job, cands=list(reversed(job['cands'])), prompt=prompt)


def step_pass2(a):
    global client_stats
    jobs = read_jsonl(p(a, 'pass2_jobs.jsonl'))
    name = 'stage1d_homonym_judgments.jsonl'
    if a.reverse:
        jobs = [reverse_job(j) for j in jobs if len(j['cands']) > 1]
        name = 'stage1d_homonym_judgments_rev.jsonl'
    cl = make_client()
    client_stats = cl.stats

    def ask(job):
        txt = cl.ask(mp.PASS2_SYSTEM, job['prompt'])
        n = len(job['cands'])
        v = mp.parse_pass2(txt, n)
        return {'window_id': job['window_id'], 'lemma': job['lemma'], 'cands': job['cands'],
                'answer': v, 'chosen': (job['cands'][v - 1] if v else None)}

    run_stage(a, jobs, ask, None, p(a, name),
              lambda r: (r['window_id'], tuple(r['cands'])), [(200, 16), (200, 24), (200, 32)])
    json.dump(cl.stats, open(p(a, 'pass2%s_gateway_%d.json' % ('rev' if a.reverse else '', int(time.time()))), 'w'))


# ------------------------------------------------------------------ eval

def load_pairs(graded_dir):
    pairs = []
    for f in GRADED:
        for q in json.load(open(os.path.join(graded_dir, f + '.json'), encoding='utf-8'))['pairs']:
            pairs.append(dict(q, file=f))
    return pairs


def pair_state(text, lang, wid, idx, t2e, amb, answers):
    trs = el.window_triggers(text, t2e[lang]).get(idx, [])
    return any(el.trigger_state(wid, idx, es, f, lang, amb, answers)[0] for _raw, f, es in trs)


def tally(res):
    def one(sel):
        c = collections.Counter()
        for (f, n), (right, kept) in res.items():
            if sel(f):
                c[('ck' if right else 'wk') if kept else ('cd' if right else 'wd')] += 1
        kept = c['ck'] + c['wk']
        return {'correct_kept': c['ck'], 'correct_dropped': c['cd'], 'wrong_kept': c['wk'], 'wrong_dropped': c['wd'],
                'kept': kept, 'precision_on_kept': round(c['ck'] / kept, 4) if kept else None}
    out = {'all': one(lambda f: True)}
    for g in GRADED:
        out[g] = one(lambda f, g=g: f == g)
    return out


def step_eval(a):
    keys, entities = load_world(a)
    types, prep = load_state(a)
    decisions = load_decisions(p(a, 'stage1d_lemma_judgments.jsonl'))
    answers = el.answers_by_index(entities, load_answers(p(a, 'stage1d_homonym_judgments.jsonl'), p(a, 'stage1d_homonym_judgments_rev.jsonl')))
    pairs = load_pairs(a.graded_dir)
    idx_of = {e['entity_id']: i for i, e in enumerate(entities)}
    texts = open_texts(a)
    tc = {q['window_id']: texts.execute('select text from window_texts where id=?', (q['window_id'],)).fetchone()[0]
          for q in pairs}
    audit_keep = {k: v for k, v in decisions.items() if v != 'keep'}
    configs = [('1b', dict(audit_fixes=False, overrides=False), None, False),
               ('1c', dict(), None, False),
               ('1d_pass1_model_decides', dict(decisions=decisions), True, False),
               ('1d_pass1_audit_drops_stand', dict(decisions=audit_keep), True, False),
               ('1d_both_passes', dict(decisions=decisions), True, True)]
    out = {'evals': {}, 'kept_by_pair': {}}
    for name, kw, use_amb, use_ans in configs:
        t2e, info = el.assemble_matcher(entities, types, prep, log=lambda *_: None, **kw)
        amb = info['amb_tokens'] if use_amb else None
        res = {}
        for q in pairs:
            kept = pair_state(tc[q['window_id']], q['lang'], q['window_id'], idx_of[q['entity_id']], t2e, amb,
                              answers if use_ans else None)
            res[(q['file'], q['n'])] = (q['verdict'] == 'right', kept)
        out['evals'][name] = tally(res)
        out['kept_by_pair'][name] = {f'{f}#{n}': k for (f, n), (r, k) in res.items()}
        print(name, json.dumps(out['evals'][name]['all']), flush=True)
    out['pairs'] = [{k: q[k] for k in ('file', 'n', 'window_id', 'entity_id', 'token', 'lang', 'verdict')} for q in pairs]
    json.dump(out, open(p(a, 'stage1d_eval.json'), 'w'), ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ build and draw

def step_build(a):
    keys = json.load(open(a.entities_json, encoding='utf-8'))
    decisions = load_decisions(p(a, 'stage1d_lemma_judgments.jsonl'))
    answers = load_answers(p(a, 'stage1d_homonym_judgments.jsonl'), p(a, 'stage1d_homonym_judgments_rev.jsonl'))
    counts, _rows, _ents = ei.build_store(keys, a.passage_dir, a.out, matcher='lemma',
                                          lemma_decisions=decisions, homonym_answers=answers)
    print('mentions by language', counts['list_mentions_by_language'], 'windows', counts['windows_with_mentions'])


def step_draw(a):
    excl = set()
    for f in GRADED + EXTRA_EXCLUDE:
        for q in json.load(open(os.path.join(a.graded_dir, f + '.json'), encoding='utf-8'))['pairs']:
            excl.add(q['window_id'])
    db = sqlite3.connect(f'file:{a.out}?mode=ro', uri=True)
    rows = db.execute("select e.entity_id, w.window_id, m.form, e.label, e.type, w.language from mention_rows m "
                      "join entities e on e.eid=m.eid join windows w on w.wid=m.wid where e.source='list' "
                      "order by e.entity_id, w.window_id").fetchall()
    rows = [r for r in rows if r[1] not in excl]
    pick = random.Random(a.seed).sample(rows, 40)
    json.dump([dict(zip(['entity_id', 'window_id', 'token', 'label', 'type', 'lang'], r)) for r in pick],
              open(p(a, 'fresh40_drawn.json'), 'w'), ensure_ascii=False, indent=0)
    print(len(rows), 'candidate rows; drew 40 with seed', a.seed)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', choices=['prepare', 'pass1', 'plan2', 'pass2', 'eval', 'build', 'draw'])
    ap.add_argument('--entities-json')
    ap.add_argument('--passage-dir', default=os.path.join(ROOT, 'data', 'passage_index'))
    ap.add_argument('--audit-csv')
    ap.add_argument('--graded-dir')
    ap.add_argument('--work-dir', required=True)
    ap.add_argument('--store', help='the stage 1c store (a candidate\'s works)')
    ap.add_argument('--pleiades-places')
    ap.add_argument('--out', help='store to write (build) or read (draw)')
    ap.add_argument('--threads', type=int, default=8)
    ap.add_argument('--reverse', action='store_true', help='pass2: ask the multi-candidate questions again with the candidates in reverse order')
    ap.add_argument('--fixed-threads', type=int, default=0, help='after the probe segments, use this many threads')
    ap.add_argument('--probe-jobs', type=int, default=0, help='size of the segment run at --fixed-threads (default 1000)')
    ap.add_argument('--budget', type=int, default=480, help='seconds a pass step may run')
    ap.add_argument('--seed', type=int, default=20261020)
    a = ap.parse_args()
    os.makedirs(a.work_dir, exist_ok=True)
    globals()['step_' + a.step](a)
    return 0


if __name__ == '__main__':
    sys.exit(main())
