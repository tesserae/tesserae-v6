"""Stage 3b: the oblique-case recall gap, English search names, near spellings and three label faults
(2026-10-17). Every step reads and writes files in --work-dir (private), so a gateway step cut off by its
time budget picks up where it stopped.

    venv/bin/python scripts/entity_stage3b.py STEP --work-dir research/entities/stage3b_work [...]

STEP, in order:
    measure     which lemmas the case-form rule adds to each list entity, the lines they add, the
                twenty entities that lose most, and the pass-one questions for the new pairs
                (about 6 minutes, under 4 GB)
    pairs       ask the gateway about each new (entity, lemma) pair         (--budget SECONDS, resumable)
    plan2       find the windows with an ambiguous name once the pairs are applied and write the
                pass-two questions                                          (about 2 minutes)
    pass2       ask which candidate each window names (--reverse for the second order)
    eval        the fixed graded pairs under the new matcher
    names       ask the English and other search names of every list and promoted entity
    labels      the questions for the label faults
    The case-form extension is OFF unless --case-forms is given to plan2 and build. The installed store is the
    one built without it. The extension is a measured option (stage 3b report, fix pass).
    (the store itself is built by entity_model_pass.py build, build_entity_index.py and
    entity_promote.py build, see the stage 3b report)

The gateway address and key are read by backend/entity_gateway.py from the production .env and are never
printed or written. The judgments stay in --work-dir, which is private; this script carries no data.
"""
import argparse
import collections
import json
import os
import pickle
import random
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from backend import entity_index as ei  # noqa: E402
from backend import entity_lemma as el  # noqa: E402
from backend import entity_model_pass as mp  # noqa: E402
import entity_model_pass as emp  # noqa: E402

SEED_SNIPPETS = 20261023
SNIPPETS = 3


def p(a, name):
    return os.path.join(a.work_dir, name)


def read_jsonl(path):
    return emp.read_jsonl(path)


def judgment_files(a, name):
    """Stage 1d, stage 2 (read only) and stage 3b judgment files of one kind."""
    import glob
    out = [os.path.join(d, name) for d in (a.reuse_dir or [])]
    out.append(p(a, name))
    base = p(a, name)[:-len('.jsonl')]
    out.extend(sorted(glob.glob(base + '.[st][0-9]*.jsonl')))
    return out


def load_world(a):
    keys = json.load(open(a.entities_json, encoding='utf-8'))
    entities, _ = ei.merge_list_entities(keys)
    return keys, entities


def load_decisions(a):
    return emp.load_decisions(judgment_files(a, 'stage1d_lemma_judgments.jsonl'))


def load_state(a):
    st = pickle.load(open(a.state, 'rb'))
    return st['types'], st['prep']


def work_languages(texts):
    return dict(texts.execute('select distinct work, language from window_texts'))


# ------------------------------------------------------------------ measure

def step_measure(a):
    t0 = time.time()
    keys, entities = load_world(a)
    types, prep = load_state(a)
    dec = load_decisions(a)
    quiet = lambda *_: None  # noqa: E731
    t2e0, info0 = el.assemble_matcher(entities, types, prep, decisions=dec, log=quiet)
    t2e1, info1 = el.assemble_matcher(entities, types, prep, decisions=dec, case_forms=True, log=quiet)
    ext = info1['extension']
    print(f'{len(ext)} new (entity, lemma) pairs before the audit; matcher built {time.time() - t0:.0f}s', flush=True)
    survive = {k for k in ext if k[2] in info1['ent_lemmas'][k[0]].get(k[1], ())}
    by_lang = collections.Counter(k[0] for k in ext)
    surv_lang = collections.Counter(k[0] for k in survive)
    print('pairs by language', dict(by_lang), 'surviving the audit', dict(surv_lang), flush=True)

    # token -> new pairs, for the example lines and forms
    tokpairs = collections.defaultdict(list)
    for (lang, idx, lem), toks in ext.items():
        for t in toks:
            tokpairs[(lang, t)].append((lang, idx, lem))
    # entities that gain a token in the matcher (after audit and decisions)
    gained = {lg: {} for lg in ei.LANGS}
    for lg in ei.LANGS:
        for tok, es in t2e1[lg].items():
            new = set(es) - set(t2e0[lg].get(tok, ()))
            if new:
                gained[lg][tok] = new
    texts = emp.open_texts(a)
    wl = work_languages(texts)
    rnd = random.Random(SEED_SNIPPETS)
    seen = collections.Counter()
    snip = collections.defaultdict(list)
    forms = collections.defaultdict(collections.Counter)
    lines_added = collections.defaultdict(collections.Counter)      # lang -> idx -> lines
    distinct_lines = collections.Counter()
    n = 0
    for work, ref, text in texts.execute('select work, ref, text from lines'):
        lang = wl.get(work)
        if lang not in el.CASE_LANGS:
            continue
        n += 1
        old_in_line = set()
        new_in_line = set()
        t2e = t2e0[lang]
        g = gained[lang]
        for raw, f, initial in el.tokens_of(text):
            if not el.is_cap(raw):
                continue
            es = t2e.get(f)
            if es:
                old_in_line.update(es)
            gn = g.get(f)
            if gn:
                new_in_line.update(gn)
            pl = tokpairs.get((lang, f))
            if pl:
                for pr in pl:
                    forms[pr][raw] += 1
                    seen[pr] += 1
                    if initial:
                        continue
                    if len(snip[pr]) < SNIPPETS:
                        snip[pr].append(mp.line_snippet(text, raw))
                    else:
                        j = rnd.randrange(seen[pr])
                        if j < SNIPPETS:
                            snip[pr][j] = mp.line_snippet(text, raw)
        add = new_in_line - old_in_line
        if add:
            distinct_lines[lang] += 1
            for i in add:
                lines_added[lang][i] += 1
        if n % 500000 == 0:
            print(f'  scanned {n} lines {time.time() - t0:.0f}s', flush=True)
    print(f'lines scanned {n}, {time.time() - t0:.0f}s', flush=True)

    # the twenty entities that lose most
    per_entity = collections.defaultdict(lambda: {'la': 0, 'grc': 0})
    for lg in el.CASE_LANGS:
        for i, c in lines_added[lg].items():
            per_entity[i][lg] = c
    rows = []
    for i, d in per_entity.items():
        e = entities[i]
        newl = {lg: sorted(lem for (g, ix, lem) in survive if g == lg and ix == i) for lg in el.CASE_LANGS}
        rows.append({'entity_id': e['entity_id'], 'label': e['label'], 'type': e['type'], 'lines_la': d['la'],
                     'lines_grc': d['grc'], 'lines': d['la'] + d['grc'], 'new_lemmas': newl})
    rows.sort(key=lambda r: -r['lines'])
    tot = {lg: sum(lines_added[lg].values()) for lg in el.CASE_LANGS}
    out = {'pairs_before_audit': len(ext), 'pairs_before_audit_by_language': dict(by_lang),
           'pairs_after_audit': len(survive), 'pairs_after_audit_by_language': dict(surv_lang),
           'entities_with_new_lemmas': len({k[1] for k in ext}),
           'entities_losing_lines': len(rows),
           'entity_lines_lost_by_language': tot,
           'distinct_lines_lost_by_language': dict(distinct_lines),
           'top20': rows[:20], 'seconds': round(time.time() - t0)}
    json.dump(out, open(p(a, 'recall_measurement.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump(rows, open(p(a, 'recall_measurement_all.json'), 'w'), ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if k != 'top20'}), flush=True)
    for r in rows[:20]:
        print(r['label'], r['entity_id'], r['lines_la'], r['lines_grc'], r['new_lemmas'], flush=True)
    for r in rows:
        if r['label'].startswith('Rhod'):
            print('RHODES', r, flush=True)

    # pass-one questions for the new pairs without a decision
    jobs = []
    skipped = 0
    decided = el.decisions_by_index(entities, dec)
    for (lang, idx, lem) in sorted(ext, key=lambda k: (entities[k[1]]['entity_id'], k[0], k[2])):
        e = entities[idx]
        if (lang, idx, lem) in decided:
            skipped += 1
            continue
        fs = [w for w, _ in forms[(lang, idx, lem)].most_common(3)]
        if not fs:
            fs = list(ext[(lang, idx, lem)])[:3]
        user = mp.pass1_prompt(e, lem, lang, fs, snip[(lang, idx, lem)])
        jobs.append({'entity_id': e['entity_id'], 'lang': lang, 'lemma': lem, 'prompt': user,
                     'audit_action': 'kept_by_audit' if (lang, idx, lem) in survive else 'dropped_by_audit',
                     'tokens': ext[(lang, idx, lem)][:6]})
    emp.write_jsonl(p(a, 'pass1_jobs.jsonl'), jobs)
    print(f'{len(jobs)} pass-one questions written ({skipped} pairs already judged), {time.time() - t0:.0f}s', flush=True)


# ------------------------------------------------------------------ pairs

def step_pairs(a):
    jobs = read_jsonl(p(a, 'pass1_jobs.jsonl'))
    cl = emp.make_client()
    emp.client_stats = cl.stats

    def ask(job):
        txt = cl.ask(mp.PASS1_SYSTEM, job['prompt'])
        return {'entity_id': job['entity_id'], 'lang': job['lang'], 'lemma': job['lemma'], 'answer': mp.parse_pass1(txt)}

    emp.run_stage(a, jobs, ask, None, p(a, 'stage1d_lemma_judgments.jsonl'),
                  lambda r: (r['lang'], r['entity_id'], r['lemma']), [(200, 16), (200, 48)])
    json.dump(cl.stats, open(p(a, 'pairs_gateway_%d.json' % int(time.time())), 'w'))


# ------------------------------------------------------------------ plan pass two

def answers_index(a, entities):
    fwd = emp.read_jsonl_all(judgment_files(a, 'stage1d_homonym_judgments.jsonl'))
    rev = emp.read_jsonl_all(judgment_files(a, 'stage1d_homonym_judgments_rev.jsonl'))
    return el.reuse_answers(entities, fwd, rev)


def step_plan2(a):
    t0 = time.time()
    keys, entities = load_world(a)
    types, prep = load_state(a)
    dec = load_decisions(a)
    t2e, info = el.assemble_matcher(entities, types, prep, decisions=dec, case_forms=a.case_forms, case_allowed=load_allowed(a) if a.case_forms else None,
                                     log=lambda *_: None)
    texts = emp.open_texts(a)
    ids = json.load(open(os.path.join(a.passage_dir, 'ids.json')))
    unit = ei.unit_windows(ids)
    del ids
    collect = {}
    answers, asked = answers_index(a, entities)
    rows, wmeta, tally = el.scan_windows_lemma(texts, unit, t2e, amb_tokens=info['amb_tokens'], answers=answers,
                                               collect=collect)
    n_collected = len(collect)
    collect = {k: v for k, v in collect.items() if k not in asked}
    print(f'{n_collected} windows with an unresolved ambiguous name, {len(collect)} never put to the model', flush=True)
    by_lang = collections.Counter(r['lang'] for r in rows)
    print('table: mentions', len(rows), dict(by_lang), 'diag', json.dumps(info['diag']), flush=True)
    idxs = sorted({i for (_w, es) in collect for i in es})
    desc = emp.describe_candidates(a, entities, idxs)
    jobs = []
    mentions_asked = 0
    for (wid, es), (raw, lang, text) in sorted(collect.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        cands = [desc[i] for i in es]
        f = ei._fold_tok(raw)
        jobs.append({'window_id': wid, 'lemma': info['type_lemma'][lang].get(f, f), 'lang': lang,
                     'cands': [entities[i]['entity_id'] for i in es], 'raw': raw,
                     'prompt': mp.pass2_prompt(mp.clip_words(text, raw), raw, cands)})
        mentions_asked += len(es)
    emp.write_jsonl(p(a, 'pass2_jobs.jsonl'), jobs)
    summ = {'questions': len(jobs), 'unresolved_windows_before_filter': n_collected, 'mentions_covered_upper_bound': mentions_asked,
            'questions_by_language': dict(collections.Counter(j['lang'] for j in jobs)),
            'candidates_per_question': dict(collections.Counter(len(j['cands']) for j in jobs)),
            'table_mentions': len(rows), 'table_by_language': dict(by_lang),
            'windows_with_list_mention': len({r['wid'] for r in rows}),
            'homonym_flagged_mentions': sum(1 for r in rows if r['homonym']),
            'seconds': round(time.time() - t0)}
    json.dump(summ, open(p(a, 'plan2_summary.json'), 'w'), indent=1)
    print(json.dumps(summ, indent=1), flush=True)


def step_pass2(a):
    jobs = read_jsonl(p(a, 'pass2_jobs.jsonl'))
    name = 'stage1d_homonym_judgments.jsonl'
    if a.reverse:
        jobs = [emp.reverse_job(j) for j in jobs if len(j['cands']) > 1]
        name = 'stage1d_homonym_judgments_rev.jsonl'
    if a.shard:
        k, n = (int(x) for x in a.shard.split('/'))
        # the shard is fixed by the question's place in the full list, so shards started a few seconds
        # apart never overlap or leave a gap
        jobs = [j for i, j in enumerate(jobs) if i % n == k]
        have = {(r['window_id'], tuple(r['cands'])) for r in emp.read_jsonl_all(
            [f for f in judgment_files(a, name) if os.path.dirname(f) == a.work_dir.rstrip('/')]) if r.get('answer') is not None}
        jobs = [j for j in jobs if (j['window_id'], tuple(j['cands'])) not in have]
        name = name[:-len('.jsonl')] + '.t%d_%d.jsonl' % (n, k)
    cl = emp.make_client()
    emp.client_stats = cl.stats

    def ask(job):
        txt = cl.ask(mp.PASS2_SYSTEM, job['prompt'])
        v = mp.parse_pass2(txt, len(job['cands']))
        return {'window_id': job['window_id'], 'lemma': job['lemma'], 'cands': job['cands'],
                'answer': v, 'chosen': (job['cands'][v - 1] if v else None)}

    emp.run_stage(a, jobs, ask, None, p(a, name), lambda r: (r['window_id'], tuple(r['cands'])),
                  [(200, 16), (200, 48)])
    json.dump(cl.stats, open(p(a, 'pass2%s_gateway_%d.json' % ('rev' if a.reverse else '', int(time.time()))), 'w'))


# ------------------------------------------------------------------ search names

NAMES_SYSTEM = (
    'You help people search a catalog of ancient people, places, gods and peoples. You are given one entry with its '
    'labels, its type, a description when there is one, and spellings found in the texts. Reply with one JSON list of '
    'strings and nothing else. The first string is the usual English name of the entry, the one an English-speaking '
    'reader would type (Rhodes for Rhodos, Athens for Athenae, Marseille for Massilia). Then up to three other names or '
    'spellings a reader might type, in English, Latin, Greek or transliterated, each different from the first. If the '
    'usual English name is the label itself, give it first anyway.')


def names_question(row, forms):
    lines = [f"Label: {row['label']}" + (f" · {row['greek']}" if row['greek'] else ''), f"Type: {row['type']}"]
    if row['description']:
        lines.append(f"Description: {row['description']}")
    if forms:
        lines.append('Spellings found: ' + ', '.join(forms))
    return '\n'.join(lines)


def parse_names(text):
    """The list of names (at most four, the usual English name first), or None for an unusable reply."""
    import re
    if not text:
        return None
    t = re.sub(r'^```(?:json)?|```$', '', text.strip(), flags=re.M).strip()
    a, b = t.find('['), t.rfind(']')
    if a < 0 or b <= a:
        return None
    try:
        arr = json.loads(t[a:b + 1])
    except ValueError:
        return None
    if not isinstance(arr, list):
        return None
    out = []
    for x in arr:
        x = re.sub(r'\s+', ' ', str(x or '')).strip()
        if x and len(x) <= 60 and x.lower() not in {o.lower() for o in out}:
            out.append(x)
    return out[:4] if out else None


def step_names(a):
    db = sqlite3.connect(f'file:{a.store}?mode=ro', uri=True)
    rows = db.execute("select e.eid, e.entity_id, e.source, e.type, e.label, l.display_label_grc, l.description "
                      "from entities e left join entity_labels l on l.eid = e.eid "
                      "where e.source in ('list', 'promoted') order by e.entity_id").fetchall()
    forms = collections.defaultdict(list)
    for eid, f in db.execute("select eid, form from variants where source in ('list', 'promoted', 'names') order by rowid"):
        forms[eid].append(f)
    jobs = []
    for eid, ent, src, typ, label, grc, desc in rows:
        r = {'label': label, 'greek': grc, 'type': typ, 'description': desc}
        jobs.append({'entity_id': ent, 'source': src, 'label': label,
                     'prompt': names_question(r, forms[eid][:6])})
    cl = emp.make_client()
    emp.client_stats = cl.stats

    def ask(job):
        txt = cl.ask(NAMES_SYSTEM, job['prompt'], max_tokens=120)
        names = parse_names(txt)
        return {'entity_id': job['entity_id'], 'source': job['source'], 'label': job['label'], 'answer': names,
                'reply': txt if names is None else None}

    import glob
    done = {r['entity_id'] for f in [p(a, 'search_names.jsonl')] + glob.glob(p(a, 'search_names.s[0-9]*.jsonl'))
            for r in read_jsonl(f) if r.get('answer')}
    jobs = [j for j in jobs if j['entity_id'] not in done]
    name = 'search_names.jsonl'
    if a.shard:
        k, n = (int(x) for x in a.shard.split('/'))
        jobs = [j for i, j in enumerate(jobs) if i % n == k]
        name = 'search_names.s%d.jsonl' % k
    emp.run_stage(a, jobs, ask, None, p(a, name), lambda r: r['entity_id'], [(200, 16), (200, 48)])
    json.dump(cl.stats, open(p(a, 'names_gateway_%d.json' % int(time.time())), 'w'))


# ------------------------------------------------------------------ build

def step_build(a):
    """The stage 2 store with the case-form lemma sets: every judgment of stages 1d, 2 and 3b applied."""
    keys = json.load(open(a.entities_json, encoding='utf-8'))
    decisions = load_decisions(a)
    counts, _rows, _ents = ei.build_store(keys, a.passage_dir, a.out, matcher='lemma', lemma_decisions=decisions,
                                          answers_loader=lambda ents: answers_index(a, ents)[0], case_forms=a.case_forms,
                                          case_allowed=load_allowed(a) if a.case_forms else None)
    print('mentions by language', counts['list_mentions_by_language'], 'windows', counts['windows_with_mentions'])


def step_docs(a):
    """Copy the inscriptions and papyri table (document_mentions and its meta rows) from the stage 2b
    store into --out. The table depends on the entities' names and forms and on the documents index,
    not on the mention rows, so the stage 2b build stays valid. Every entity of --out must have the
    same id and eid in the source, else nothing is copied."""
    from backend import entity_extras as ex
    src = sqlite3.connect(f'file:{a.store}?mode=ro', uri=True)
    dst = sqlite3.connect(a.out)
    a_ent = dict(src.execute('select entity_id, eid from entities'))
    b_ent = dict(dst.execute('select entity_id, eid from entities'))
    diff = [k for k in b_ent if a_ent.get(k) != b_ent[k]]
    if diff:
        raise SystemExit(f'REFUSING: {len(diff)} entities differ in id or eid between the stores, e.g. {diff[:5]}')
    forms_a = {(e, f, lg) for e, f, lg in src.execute("select eid, form, language from variants where source in ('list', 'names')")}
    forms_b = {(e, f, lg) for e, f, lg in dst.execute("select eid, form, language from variants where source in ('list', 'names')")}
    labels_a = dict(src.execute("select eid, label from entities where source in ('list', 'names')"))
    labels_b = dict(dst.execute("select eid, label from entities where source in ('list', 'names')"))
    if forms_a != forms_b or labels_a != labels_b:
        raise SystemExit('REFUSING: the entities of the two stores have different forms or labels')
    dst.executescript(ex.DOC_SCHEMA)
    dst.execute('delete from document_mentions')
    rows = src.execute('select * from document_mentions').fetchall()
    dst.executemany('insert into document_mentions values (?,?,?,?,?,?)', rows)
    dst.execute(ex.DOC_INDEX)
    for k, v in src.execute("select key, value from meta where key in ('document_mentions', 'documents_fingerprint', "
                            "'document_mentions_seconds')"):
        dst.execute('delete from meta where key = ?', (k,))
        dst.execute('insert into meta values (?, ?)', (k, v))
    dst.commit()
    print(f'{len(rows)} document rows copied; {len(b_ent)} entities checked')


def step_searchnames(a):
    """Store the model's search names for every list and promoted entity in --out as the table
    search_names(eid, name, source) and rebuild the catalog. Names are for search only."""
    import glob
    from backend import entity_extras as ex
    rows = {}
    for f in [p(a, 'search_names.jsonl')] + sorted(glob.glob(p(a, 'search_names.s[0-9]*.jsonl'))):
        for r in read_jsonl(f):
            if r.get('answer'):
                rows[r['entity_id']] = r['answer']
    db = sqlite3.connect(a.out)
    eids = dict(db.execute("select entity_id, eid from entities where source in ('list', 'promoted')"))
    missing = [k for k in eids if k not in rows]
    db.executescript('DROP TABLE IF EXISTS search_names; CREATE TABLE search_names (eid INTEGER, name TEXT, source TEXT);')
    n = 0
    for ent, names in rows.items():
        eid = eids.get(ent)
        if eid is None:
            continue
        for nm in names:
            db.execute('insert into search_names values (?,?,?)', (eid, nm, 'model'))
            n += 1
    db.execute('CREATE INDEX ix_sn_eid ON search_names(eid)')
    db.execute("delete from meta where key = 'search_names'")
    db.execute("insert into meta values ('search_names', ?)", (json.dumps({'entities': len(rows), 'names': n, 'missing': len(missing)}),))
    db.commit()
    db.close()
    ex.write_catalog(a.out)
    print(f'{n} search names for {len(rows)} entities; {len(missing)} entities without an answer')
    if missing:
        json.dump(missing, open(p(a, 'search_names_missing.json'), 'w'))


# ------------------------------------------------------------------ fix pass, gates 2 and 3

CONFIRM_SYSTEM = (
    'A catalog of ancient names is being checked. You see one entity (its label, type and listed forms) and one '
    'candidate lemma (a dictionary form written without accents), the capitalized forms in which it occurs and '
    'example lines from the corpus. Decide what the candidate is. Answer with one JSON object and nothing else, '
    '{"answer": "name" or "demonym" or "other_name" or "common"}.\n'
    'name: an inflected case form or a spelling of the entity\'s own name, so that every capitalized form of the '
    'lemma would name this entity.\n'
    'demonym: an adjective, or a word for the inhabitants, descendants or followers, made from the name.\n'
    'other_name: a different person, place, ship or group with a similar name.\n'
    'common: an ordinary word.')


def confirm_prompt(e, lemma, lang, pass1_prompt):
    """The confirmation question for one pair, from the pass-one prompt's forms and example lines."""
    forms = ''
    lines = []
    grab = False
    for ln in pass1_prompt.split('\n'):
        if ln.startswith('Most frequent capitalized forms:'):
            forms = ln.split(':', 1)[1].strip()
        elif ln == 'Example lines:':
            grab = True
        elif grab:
            lines.append(ln)
    listed = sorted({x for k in e['keys'] for x in k['latin']} | {k['greek'] for k in e['keys'] if k['greek']})
    ids = ', '.join(e.get('pleiades') or []) or 'none'
    out = [f"Entity: {e['label']} ({e['type']}; Pleiades {ids})", 'Description: none given',
           'Listed forms: ' + (', '.join(listed[:10]) or '(none)'), f'Language of the texts: {lang}',
           f'Candidate lemma: {lemma}', 'Most frequent capitalized forms: ' + (forms or '(none)'), 'Example lines:']
    out.extend(lines or ['(none)'])
    return '\n'.join(out)


def parse_confirm(text):
    import re
    if not text:
        return None
    t = re.sub(r'^```(?:json)?|```$', '', text.strip(), flags=re.M).strip()
    a, b = t.find('{'), t.rfind('}')
    if a < 0 or b <= a:
        return None
    try:
        v = str(json.loads(t[a:b + 1]).get('answer') or '').strip().lower()
    except (ValueError, AttributeError):
        return None
    return v if v in ('name', 'demonym', 'other_name', 'common') else None


def load_allowed(a):
    """{(lang, entity id, lemma)} the confirmation question called a name (gate 3)."""
    out = set()
    for r in read_jsonl(p(a, 'confirm_caseforms.jsonl')):
        if r.get('answer') == 'name':
            out.add((r['lang'], r['entity_id'], r['lemma']))
    return out


def step_gates(a):
    """Gate 2 (stem consistency) over the 4,314 pairs, the nine flipped graded pairs, how the Greek
    lemma Ellen entered Greece's candidates, and the gate 3 questions (confirm_cf_jobs.jsonl)."""
    t0 = time.time()
    keys, entities = load_world(a)
    types, prep = load_state(a)
    dec = load_decisions(a)
    quiet = lambda *_: None  # noqa: E731
    _t, info0 = el.assemble_matcher(entities, types, prep, decisions=dec, log=quiet)
    present = {lg: {i: set(v) for i, v in info0['candidate_lemmas'][lg].items()} for lg in ei.LANGS}
    why = {}
    ungated = el.case_form_extension(entities, types, prep, present, stem_gate=False, why=why)
    gated = el.case_form_extension(entities, types, prep, present, stem_gate=True)
    by_lang = collections.Counter(k[0] for k in ungated)
    pass_lang = collections.Counter(k[0] for k in gated)
    summ = {'pairs': len(ungated), 'pairs_by_language': dict(by_lang), 'pass_gate2': len(gated),
            'pass_gate2_by_language': dict(pass_lang)}
    # pass-one answers
    ans = {}
    for r in emp.read_jsonl_all(judgment_files(a, 'stage1d_lemma_judgments.jsonl')):
        ans[(r['lang'], r['entity_id'], r['lemma'])] = r.get('answer')
    g1 = {k for k in gated if ans.get((k[0], entities[k[1]]['entity_id'], k[2])) in ('yes', 'other')}
    summ['pass_gates_1_and_2'] = len(g1)
    summ['pass_gates_1_and_2_by_language'] = dict(collections.Counter(k[0] for k in g1))
    summ['pass_gate1_only'] = sum(1 for k in ungated if ans.get((k[0], entities[k[1]]['entity_id'], k[2])) in ('yes', 'other'))
    # Greece and Ellen
    byid = {e['entity_id']: i for i, e in enumerate(entities)}
    gi = byid.get('pl:1001896')
    summ['greece_hellen'] = {'listed_greek_forms': [k['greek'] for k in entities[gi]['keys'] if k['greek']],
                             'why': {f'{k[0]}:{k[2]}': v[:4] for k, v in why.items() if k[1] == gi},
                             'passes_gate2': {f'{k[0]}:{k[2]}': True for k in gated if k[1] == gi}}
    # the nine flipped pairs
    evalj = json.load(open(p(a, 'stage2_evalstore.json')))
    texts = emp.open_texts(a)
    t2e, _info = el.assemble_matcher(entities, types, prep, decisions=dec, case_forms=True, stem_gate=False, log=quiet)
    flips = []
    for c in evalj['changes']:
        i = byid[c['entity_id']]
        lang, text = texts.execute('select language, text from window_texts where id=?', (c['window_id'],)).fetchone()
        for raw, f, es in el.window_triggers(text, t2e[lang]).get(i, []):
            lem = types and prep['type_lemma'][lang].get(f)
            k = (lang, i, lem)
            flips.append({'n': c['n'], 'file': c['file'], 'verdict': c['verdict'], 'entity': entities[i]['label'], 'token': raw,
                          'lemma': lem, 'new_pair': k in ungated, 'passes_gate2': k in gated,
                          'listed_forms': sorted({fm for fm, _t2 in why.get(k, [])})[:3]})
            break
    summ['flipped'] = flips
    json.dump(summ, open(p(a, 'fixpass_gates.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summ.items() if k != 'flipped'}, ensure_ascii=False, indent=1))
    for fl in flips:
        print(json.dumps(fl, ensure_ascii=False))
    # gate 3 questions
    p1 = {(r['lang'], r['entity_id'], r['lemma']): r for r in read_jsonl(p(a, 'pass1_jobs.jsonl'))}
    jobs = []
    for k in sorted(g1, key=lambda k: (entities[k[1]]['entity_id'], k[0], k[2])):
        e = entities[k[1]]
        r = p1.get((k[0], e['entity_id'], k[2]))
        if r is None:
            continue
        jobs.append({'entity_id': e['entity_id'], 'lang': k[0], 'lemma': k[2], 'prompt': confirm_prompt(e, k[2], k[0], r['prompt'])})
    emp.write_jsonl(p(a, 'confirm_cf_jobs.jsonl'), jobs)
    print(f'{len(jobs)} confirmation questions written, {time.time() - t0:.0f}s')


def step_confirmcf(a):
    jobs = read_jsonl(p(a, 'confirm_cf_jobs.jsonl'))
    cl = emp.make_client()
    emp.client_stats = cl.stats

    def ask(job):
        txt = cl.ask(CONFIRM_SYSTEM, job['prompt'], max_tokens=40)
        return {'entity_id': job['entity_id'], 'lang': job['lang'], 'lemma': job['lemma'], 'answer': parse_confirm(txt),
                'reply': txt if parse_confirm(txt) is None else None}

    name = 'confirm_caseforms.jsonl'
    if a.shard:
        k, n = (int(x) for x in a.shard.split('/'))
        jobs = [j for i, j in enumerate(jobs) if i % n == k]
        name = 'confirm_caseforms.s%d.jsonl' % k
    emp.run_stage(a, jobs, ask, None, p(a, name), lambda r: (r['lang'], r['entity_id'], r['lemma']), [(100, 16), (100, 48)])
    json.dump(cl.stats, open(p(a, 'confirmcf_gateway_%d.json' % int(time.time())), 'w'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step')
    ap.add_argument('--entities-json', default='/home/ncoffee/licensed_text/analysis/entity_mentions/entities.json')
    ap.add_argument('--passage-dir', default=os.path.join(ROOT, 'data', 'passage_index'))
    ap.add_argument('--work-dir', required=True)
    ap.add_argument('--state', default=None, help='stage 2 state.pkl (type counts and lemmas)')
    ap.add_argument('--reuse-dir', action='append', help='earlier work folders, read only (repeat)')
    ap.add_argument('--store')
    ap.add_argument('--pleiades-places', default='/home/ncoffee/licensed_text/analysis/entity_mentions/pleiades/places.csv')
    ap.add_argument('--out')
    ap.add_argument('--threads', type=int, default=48)
    ap.add_argument('--fixed-threads', type=int, default=0)
    ap.add_argument('--probe-jobs', type=int, default=0)
    ap.add_argument('--budget', type=int, default=480)
    ap.add_argument('--reverse', action='store_true')
    ap.add_argument('--case-forms', action='store_true',
                    help='plan2, build: switch the case-form lemma extension ON (default off). The extension is a measured option, '
                         'see the fix pass in the stage 3b report. It needs confirm_caseforms.jsonl in --work-dir.')
    ap.add_argument('--shard', help='K/N: ask every Nth question, output to a separate .sK file')
    ap.add_argument('--seed', type=int, default=20261022)
    a = ap.parse_args()
    os.makedirs(a.work_dir, exist_ok=True)
    globals()['step_' + a.step](a)
    return 0


if __name__ == '__main__':
    sys.exit(main())
