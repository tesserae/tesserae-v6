"""Entity mention index: "where else is this place or person mentioned?"

Stage 1 (2026-10-17): the build and the read side, no route and no page.

The store, data/entity_index/entities.sqlite, sits beside window_names.db and is
built the same way: offline, from window_texts.db and ids.json, to a new file that is
swapped in. It holds

    entities    one row per merged entity. Source 'list' entities come from the
                proper-name list (backend/proper_names) joined to Pleiades; source
                'names' entities are the corpus's own capitalized-name keys from
                window_names.db (type 'name', no Pleiades id).
    variants    the forms each list entity is matched on, by language.
    windows     one row per passage window that carries a mention.
    mention_rows  (entity, window, form, cap, nb, ds, confidence). The view
                `mentions` joins it back to the flat shape (entity_id, window_id,
                work, ref_start, ref_end, language, form, cap, confidence).
    meta        counts, the build time and the lockstep fingerprint.

A mention (source 'list') is a whole token equal to a form of the entity or its stem
plus a closed set of case endings, folded for accents, case, j/v and final sigma, and
written with a capital initial. Windows are the "counted" windows: fine windows of
works without prose windows plus the prose-scale windows. Coarse windows are left out
because they overlap the fine ones.

Disambiguation (measured in the stage 1 report):
    a  per-entity stoplist (backend/entity_stoplists.json "forms"): a form that is a
       common word or a different name is dropped for that entity.
    b  neighbor words: a title or place word within three tokens of the name
       (backend/entity_stoplists.json "neighbor_words").
    c  description confirmation: the entity's label appears in the window's
       participants, setting or gist.
An entity is "distinctive" when its matched stem has six or more letters and it has at
most one referent. Distinctive mentions have confidence 'distinctive'. Every other
mention is 'neighbor', 'description', 'neighbor+description' or 'unconfirmed'. Nothing
here calls a model.
"""
import collections
import csv
import json
import os
import re
import sqlite3
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
STOPLIST_PATH = os.path.join(HERE, 'entity_stoplists.json')

COMB = re.compile(r'[̀-ͯ]')
TR = str.maketrans({'ς': 'σ', 'j': 'i', 'v': 'u'})
WORD = re.compile(r'[\ẁ-ͯ]+')
LANGS = ('la', 'grc', 'en')
NEIGHBOR_WINDOW = 3
DISTINCTIVE_STEM = 6

LA_END = sorted({'', 'a', 'ae', 'am', 'as', 'arum', 'is', 'o', 'e', 'us', 'i', 'um', 'os', 'orum',
                 'es', 'em', 'ibus', 'ium', 'ii', 'iis', 'ia', 'iam', 'iae', 'ius', 'ioque'},
                key=len, reverse=True)
_GR_END_RAW = ['', 'ος', 'ου', 'ω', 'ον', 'ε', 'οι', 'ων', 'οις', 'ους', 'α', 'ας', 'αν', 'η', 'ης', 'ην',
               'αι', 'αις', 'ι', 'ες', 'ευς', 'εως', 'ει', 'εα', 'ιν', 'ις', 'ιος', 'ιδος', 'ιδα', 'ιον',
               'ιου', 'ια', 'ιας', 'ιαν', 'ιαι']


def fold(t):
    t = COMB.sub('', unicodedata.normalize('NFD', str(t or '').lower())).translate(TR)
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', t)).strip()


def _fold_tok(t):
    return COMB.sub('', unicodedata.normalize('NFD', t.lower())).translate(TR)


GR_END = sorted({_fold_tok(x) for x in _GR_END_RAW}, key=len, reverse=True)


def strip_end(form, ends, minlen):
    for e in ends:
        if e and form.endswith(e) and len(form) - len(e) >= minlen:
            return form[:-len(e)]
    return form


def variants(form, ends):
    st = strip_end(form, ends, 4)
    out = {form}
    if st != form:
        out |= {st + e for e in ends if e}
    return out, st


# ---------------------------------------------------------------- stoplists

def load_stoplists(path=STOPLIST_PATH):
    """Return (forms, neighbor) where forms is {greek key: set of folded forms}
    and neighbor is {language: set of folded words}."""
    if not os.path.exists(path):
        return {}, {l: set() for l in LANGS}
    d = json.load(open(path, encoding='utf-8'))
    forms = {k: {fold(x) for x in v.get('forms', [])} for k, v in d.get('entities', {}).items()}
    nb = {l: {fold(w) for w in d.get('neighbor_words', {}).get(l, [])} for l in LANGS}
    return forms, nb


# ---------------------------------------------------------------- entities

def _label(keys):
    c = collections.Counter(k.get('english') for k in keys if k.get('english'))
    if c:
        return c.most_common(1)[0][0]
    return keys[0]['latin'][0] if keys[0]['latin'] else keys[0]['greek']


def merge_list_entities(keys):
    """Merge the proper-name list's keys (the scope's entities.json rows) into entities.

    Applied automatically: places with the same nonempty set of Pleiades ids, and keys
    with an identical English label, one type across the group and the same Pleiades
    set. Everything else that shares a label is held and written to the review rows.
    Returns (entities, review_rows). An entity is a dict with entity_id, type, label,
    pleiades (list), keys (list of key dicts)."""
    n = len(keys)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    reason = {}
    by_pl = collections.defaultdict(list)
    for i, k in enumerate(keys):
        if k['type'] == 'place' and k['pleiades']:
            by_pl[tuple(k['pleiades'])].append(i)
    for grp in by_pl.values():
        for j in grp[1:]:
            union(grp[0], j)
        if len(grp) > 1:
            for j in grp:
                reason[j] = 'pleiades'
    by_lab = collections.defaultdict(list)
    for i, k in enumerate(keys):
        lab = fold(k.get('english') or '')
        if lab:
            by_lab[lab].append(i)
    held = {}
    for lab, grp in by_lab.items():
        if len(grp) < 2:
            continue
        types = {keys[i]['type'] for i in grp}
        pls = {tuple(keys[i]['pleiades']) for i in grp}
        if len(types) == 1 and len(pls) == 1:
            for j in grp[1:]:
                union(grp[0], j)
            for j in grp:
                reason.setdefault(j, 'label')
        else:
            why = 'type' if len(types) > 1 else 'candidates'
            for j in grp:
                held[j] = why
    groups = collections.defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    entities, eid_of = [], {}
    used = set()
    for root in sorted(groups):
        mem = [keys[i] for i in groups[root]]
        pls = sorted({p for m in mem for p in m['pleiades']}, key=int)
        typ = mem[0]['type']
        eid = f'pl:{pls[0]}' if typ == 'place' and len(pls) == 1 else f'ln:{mem[0]["id"]}'
        if eid in used:
            eid = f'ln:{mem[0]["id"]}'
        used.add(eid)
        entities.append({'entity_id': eid, 'type': typ, 'label': _label(mem),
                         'pleiades': pls, 'keys': mem})
        for i in groups[root]:
            eid_of[i] = eid
    review = []
    for i, k in enumerate(keys):
        lab = fold(k.get('english') or '')
        in_label_group = lab and len(by_lab.get(lab, [])) > 1
        multi = len(groups[find(i)]) > 1
        if not (in_label_group or multi):
            continue
        if i in held:
            action, why = 'held', held[i]
        else:
            action, why = 'applied', reason.get(i, 'label')
        review.append({'key_id': k['id'], 'greek': k['greek'], 'latin': k['latin'][0] if k['latin'] else '',
                       'english': k.get('english') or '', 'type': k['type'],
                       'pleiades_candidates': len(k['pleiades']), 'group_label': lab,
                       'proposed_entity': eid_of[i], 'action': action, 'reason': why})
    return entities, review


def write_review_csv(rows, path):
    cols = ['key_id', 'greek', 'latin', 'english', 'type', 'pleiades_candidates', 'group_label',
            'proposed_entity', 'action', 'reason']
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def _english_forms(label_or_none):
    """Single-word English forms of a label: split on '/', drop parenthetical notes
    (Pleiades writes "Arar (river)" and "Gortyn(a)"), drop '?' and '*', and keep only
    pieces of four letters or more, so "(a)" and "(i)" never become the form "A" or "I"."""
    out = []
    for piece in re.split(r'/', label_or_none or ''):
        piece = re.sub(r'\s*\([^)]*\)', '', piece)
        piece = piece.replace('?', '').replace('*', '').strip()
        if piece and ' ' not in piece and len(fold(piece)) >= 4:
            out.append(piece)
    return out


def build_matchers(entities):
    """exact[lang][folded token] -> {entity index: stem length}; plus the per-entity
    homonym flags. Greek and Latin keys are matched by stem plus closed endings,
    English by the label or a Latin form with a capital initial."""
    exact = {l: collections.defaultdict(dict) for l in LANGS}

    def add(lang, tok, idx, stem):
        cur = exact[lang][tok].get(idx)
        if cur is None or stem < cur:
            exact[lang][tok][idx] = stem

    for idx, e in enumerate(entities):
        for k in e['keys']:
            for lf in k['latin']:
                f = fold(lf)
                if not f:
                    continue
                vs, st = variants(f, LA_END)
                for v in vs:
                    add('la', v, idx, len(st))
                add('en', f, idx, len(f))
            g = fold(k['greek'])
            if g:
                vs, st = variants(g, GR_END)
                for v in vs:
                    add('grc', v, idx, len(st))
            for ef in _english_forms(k.get('english')):
                add('en', fold(ef), idx, len(fold(ef)))
    return exact


def entity_flags(entities):
    """Return list of booleans, True when an entity has more than one referent: several
    Pleiades candidates, a person or deity that is also a Pleiades place, or a label
    shared with another entity."""
    lab = collections.Counter(fold(e['label']) for e in entities)
    out = []
    for e in entities:
        multi = len(e['pleiades']) > 1 or (e['type'] != 'place' and len(e['pleiades']) >= 1) \
            or lab[fold(e['label'])] > 1
        out.append(multi)
    return out


# ---------------------------------------------------------------- unit windows

def unit_windows(ids):
    """Counted windows: prose-scale windows plus fine windows of works with no
    prose-scale windows. Coarse windows and shadowed chapter windows are left out."""
    prose_works = set()
    for w in ids:
        work, scale, _ = w.rsplit(':', 2)
        if scale == 'prosem':
            prose_works.add(work)
    unit = set()
    for w in ids:
        work, scale, _ = w.rsplit(':', 2)
        if scale == 'prosem' or (scale == 'fine' and work not in prose_works):
            unit.add(w)
    return unit


# ---------------------------------------------------------------- scan

def scan_windows(texts_conn, unit, entities, exact, uncertain, stop_forms, nb_words, log=print):
    """Scan the unit windows of Latin, Greek and English.

    Returns (rows, wmeta, tally). rows: list of dicts with eidx, wid, form, nb, tok
    (the folded token), stopped (True when the stoplist removes it). wmeta: window id ->
    (language, work, ref_start, ref_end) for every unit window. Stoplisted rows are kept
    in the list with stopped=True so the caller can count and drop them."""
    # greek key -> folded stoplist forms, resolved to entity index and language-agnostic
    stop_by_idx = collections.defaultdict(set)
    for idx, e in enumerate(entities):
        for k in e['keys']:
            if k['greek'] in stop_forms:
                stop_by_idx[idx] |= stop_forms[k['greek']]
    rows, wmeta = [], {}
    tally = collections.Counter()
    t0 = time.time()
    done = 0
    q = 'select id, language, work, ref_start, ref_end, text from window_texts'
    for wid, lang, work, rs, re_, text in texts_conn.execute(q):
        if wid not in unit:
            continue
        wmeta[wid] = (lang, work, rs, re_)
        if lang not in LANGS:
            continue
        tally['windows_' + lang] += 1
        done += 1
        if done % 100000 == 0:
            log(f'  scanned {done} windows {time.time() - t0:.0f}s')
        ex = exact[lang]
        raw = WORD.findall(text)
        toks = [_fold_tok(t) for t in raw]
        hits = {}
        for pos, tk in enumerate(toks):
            s = ex.get(tk)
            if s:
                for i in s:
                    hits.setdefault(i, []).append(pos)
        if not hits:
            continue
        nbw = nb_words.get(lang) or ()
        for i, positions in hits.items():
            caps_all = [p for p in positions if raw[p][:1].isupper()]
            if not caps_all:
                continue
            stopset = stop_by_idx.get(i, ())
            caps = [p for p in caps_all if toks[p] not in stopset]
            stopped = not caps
            if stopped:
                caps = caps_all[:1]
            best, best_nb = caps[0], False
            for p in caps:
                lo, hi = max(0, p - NEIGHBOR_WINDOW), p + NEIGHBOR_WINDOW + 1
                if any(toks[j] in nbw for j in range(lo, min(hi, len(toks))) if j != p):
                    best, best_nb = p, True
                    break
            tok = toks[best]
            rows.append({'eidx': i, 'wid': wid, 'form': raw[best], 'tok': tok, 'nb': best_nb,
                         'stem': ex[tok][i], 'stopped': stopped, 'lang': lang})
    tally['scan_seconds'] = round(time.time() - t0)
    return rows, wmeta, tally


def description_hits(desc_path, wanted, exact, log=print):
    """For windows in `wanted` (id -> set of entity indexes), return the set of
    (wid, eidx) whose entity label appears with a capital initial in the window's
    participants, setting or gist. Streams the jsonl, parsing only wanted lines."""
    found = set()
    t0 = time.time()
    n = 0
    with open(desc_path, encoding='utf-8') as f:
        for line in f:
            if not line.startswith('{"id": "'):
                continue
            end = line.index('"', 8)
            wid = line[8:end]
            need = wanted.get(wid)
            if not need:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            desc = d.get('desc') or {}
            text = ' '.join(str(desc.get(k) or '') for k in ('participants', 'setting', 'gist'))
            n += 1
            for raw in WORD.findall(text):
                if not raw[:1].isupper():
                    continue
                tk = _fold_tok(raw)
                for lang in ('en', 'la'):
                    s = exact[lang].get(tk)
                    if s:
                        for i in s:
                            if i in need:
                                found.add((wid, i))
    log(f'  description pass: {n} windows read, {len(found)} confirmations, {time.time() - t0:.0f}s')
    return found


def confidence_of(distinctive, nb, ds):
    if distinctive:
        return 'distinctive'
    if nb and ds:
        return 'neighbor+description'
    if nb:
        return 'neighbor'
    if ds:
        return 'description'
    return 'unconfirmed'


# ---------------------------------------------------------------- names source

def import_names(names_path, unit, wmeta_langs, log=print):
    """Read window_names.db and return (name_entities, name_rows). name_entities:
    {key: {'label', 'df', 'forms': Counter}}; name_rows: list of (key, wid, form) for
    windows in `unit` (one row per key and window)."""
    c = sqlite3.connect(f'file:{names_path}?mode=ro', uri=True)
    ents = {}
    seen = set()
    rows = []
    forms = collections.defaultdict(collections.Counter)
    for wid, k, form in c.execute('select id, k, form from window_names'):
        if wid not in unit or not k:
            continue
        if (wid, k) in seen:
            continue
        seen.add((wid, k))
        forms[k][form] += 1
        rows.append((k, wid, form))
    df = dict(c.execute('select k, df from name_df'))
    meta = dict(c.execute('select key, value from meta'))
    for k, fc in forms.items():
        ents[k] = {'label': fc.most_common(1)[0][0], 'df': df.get(k, 0), 'forms': fc}
    c.close()
    return ents, rows, meta


def name_key_for(entity, name_keys, keyfn):
    """The names-store key of a list entity: of the keys of its forms, the one
    with the largest document frequency, or None."""
    best, best_df = None, -1
    for k in entity['keys']:
        for f in k['latin'] + [k['greek'], k.get('english') or ''] :
            for tok in f.split():
                if len(tok) < 3:
                    continue
                try:
                    kk = keyfn(tok)
                except Exception:  # noqa: BLE001
                    kk = None
                if kk and kk in name_keys and name_keys[kk] > best_df:
                    best, best_df = kk, name_keys[kk]
    return best


# ---------------------------------------------------------------- store

SCHEMA = '''
CREATE TABLE entities (
  eid INTEGER PRIMARY KEY, entity_id TEXT UNIQUE, type TEXT, label TEXT, source TEXT,
  pleiades_id TEXT, pleiades_candidates TEXT, prosopography_id TEXT, homonym_group TEXT,
  name_key TEXT, distinctive INTEGER, n_windows INTEGER);
CREATE TABLE variants (eid INTEGER, form TEXT, language TEXT, role TEXT, source TEXT);
CREATE TABLE windows (wid INTEGER PRIMARY KEY, window_id TEXT UNIQUE, work TEXT, ref_start TEXT,
  ref_end TEXT, language TEXT);
CREATE TABLE mention_rows (eid INTEGER, wid INTEGER, form TEXT, cap INTEGER, nb INTEGER, ds INTEGER,
  confidence TEXT);
CREATE TABLE meta (key TEXT, value TEXT);
CREATE VIEW mentions AS
  SELECT e.entity_id, w.window_id, w.work, w.ref_start, w.ref_end, w.language, m.form, m.cap, m.confidence
  FROM mention_rows m JOIN entities e ON e.eid = m.eid JOIN windows w ON w.wid = m.wid;
'''
INDEXES = '''
CREATE INDEX ix_mr_eid ON mention_rows(eid);
CREATE INDEX ix_mr_wid ON mention_rows(wid);
CREATE INDEX ix_ent_label ON entities(label);
CREATE INDEX ix_ent_pleiades ON entities(pleiades_id);
CREATE INDEX ix_ent_name_key ON entities(name_key);
CREATE INDEX ix_var_eid ON variants(eid);
CREATE INDEX ix_win_work ON windows(work);
'''


def fingerprint(ids_path, names_path):
    """Counts the lockstep check compares: counted windows in ids.json and the window
    count window_names.db records in its meta table."""
    ids = json.load(open(ids_path))
    unit = unit_windows(ids)
    nm = None
    if names_path and os.path.exists(names_path):
        c = sqlite3.connect(f'file:{names_path}?mode=ro', uri=True)
        nm = dict(c.execute('select key, value from meta')).get('windows')
        c.close()
    return {'ids_total': len(ids), 'unit_windows': len(unit), 'names_windows_meta': nm}


def check_lockstep(store_path, passage_dir):
    """Return a list of problems (empty when the entity store is in step with the
    passage index and the names store)."""
    problems = []
    if not os.path.exists(store_path):
        return [f'entity store missing: {store_path}']
    ids_path = os.path.join(passage_dir, 'ids.json')
    names_path = os.path.join(passage_dir, 'window_names.db')
    now = fingerprint(ids_path, names_path)
    c = sqlite3.connect(f'file:{store_path}?mode=ro', uri=True)
    meta = dict(c.execute('select key, value from meta'))
    c.close()
    for key in ('ids_total', 'unit_windows', 'names_windows_meta'):
        if str(now[key]) != str(meta.get(key)):
            problems.append(f'{key}: passage index has {now[key]}, entity store was built at {meta.get(key)}')
    return problems


# ---------------------------------------------------------------- read side

def open_store(path):
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


def find_entities(conn, text, limit=20):
    """Entities whose label or a variant equals `text` (case and accent folded), most
    windows first."""
    f = fold(text)
    out = {}
    for eid, ent_id, typ, label, n in conn.execute(
            'select eid, entity_id, type, label, n_windows from entities'
            ' where lower(label) = ? or label = ?', (text.lower(), text)):
        out[eid] = (ent_id, typ, label, n)
    for (eid,) in conn.execute('select distinct eid from variants where form = ?', (f,)):
        r = conn.execute('select entity_id, type, label, n_windows from entities where eid=?', (eid,)).fetchone()
        if r:
            out[eid] = r
    return sorted(out.values(), key=lambda r: -(r[3] or 0))[:limit]


def mentions_of(conn, entity_id, language=None, work=None, min_confidence=None, limit=None):
    """Mention rows of one entity. min_confidence 'confirmed' keeps distinctive, neighbor
    and description rows and drops 'unconfirmed'."""
    sql = ('select window_id, work, ref_start, ref_end, language, form, cap, confidence'
           ' from mentions where entity_id = ?')
    args = [entity_id]
    if language:
        sql += ' and language = ?'
        args.append(language)
    if work:
        sql += ' and work = ?'
        args.append(work)
    if min_confidence == 'confirmed':
        sql += " and confidence != 'unconfirmed'"
    if limit:
        sql += f' limit {int(limit)}'
    return conn.execute(sql, args).fetchall()


def counts_by_work(conn, entity_id):
    return conn.execute(
        'select w.work, count(*) from mention_rows m join entities e on e.eid=m.eid'
        ' join windows w on w.wid=m.wid where e.entity_id=? group by w.work order by 2 desc',
        (entity_id,)).fetchall()


# ---------------------------------------------------------------- build

_GR = {'α': 'a', 'β': 'b', 'γ': 'g', 'δ': 'd', 'ε': 'e', 'ζ': 'z', 'η': 'e', 'θ': 'th', 'ι': 'i', 'κ': 'k',
       'λ': 'l', 'μ': 'm', 'ν': 'n', 'ξ': 'ks', 'ο': 'o', 'π': 'p', 'ρ': 'r', 'σ': 's', 'ς': 's', 'τ': 't',
       'υ': 'u', 'φ': 'f', 'χ': 'kh', 'ψ': 'ps', 'ω': 'o'}


def names_key(tok):
    """Same key as scripts/corpus/build_window_names.py key(): accent-stripped, Greek
    transliterated, first five letters. Keep the two in step."""
    t = COMB.sub('', unicodedata.normalize('NFD', tok)).lower()
    t = ''.join(_GR.get(c, c) for c in t)
    t = re.sub(r'[^a-z]', '', t)
    for a, b in (('ph', 'f'), ('th', 't'), ('ch', 'kh'), ('ae', 'ai'), ('oe', 'oi'), ('c', 'k'),
                 ('y', 'u'), ('x', 'ks'), ('j', 'i'), ('v', 'u')):
        t = t.replace(a, b)
    return t[:5] if len(t) >= 4 else None


def build_store(keys, passage_dir, out_path, stoplist_path=STOPLIST_PATH, review_csv=None,
                apply_stoplist=True, log=print):
    """Build the whole store from scratch into out_path (replaced if present).

    keys: the proper-name list as the scope's entity rows (id, greek, latin, english, type,
    pleiades). passage_dir: a folder with ids.json, window_texts.db, window_names.db and
    descriptions.jsonl. Returns the counts dict (also written to the meta table)."""
    t0 = time.time()
    counts = {}
    entities, review = merge_list_entities(keys)
    if review_csv:
        write_review_csv(review, review_csv)
    counts['list_keys'] = len(keys)
    counts['entities_list'] = len(entities)
    counts['entities_list_by_type'] = dict(collections.Counter(e['type'] for e in entities))
    counts['review_rows'] = len(review)
    counts['review_held'] = sum(1 for r in review if r['action'] == 'held')
    log(f"entities: {len(keys)} keys -> {len(entities)} entities {counts['entities_list_by_type']}")

    exact = build_matchers(entities)
    multi = entity_flags(entities)
    stop_forms, nb_words = load_stoplists(stoplist_path)
    if not apply_stoplist:
        stop_forms = {}

    ids = json.load(open(os.path.join(passage_dir, 'ids.json')))
    unit = unit_windows(ids)
    counts['ids_total'] = len(ids)
    counts['unit_windows'] = len(unit)
    del ids
    texts = sqlite3.connect(f"file:{os.path.join(passage_dir, 'window_texts.db')}?mode=ro", uri=True)
    rows, wmeta, tally = scan_windows(texts, unit, entities, exact, None, stop_forms, nb_words, log=log)
    texts.close()
    counts.update({k: v for k, v in tally.items()})
    counts['mentions_before_stoplist'] = len(rows)
    rows_kept = [r for r in rows if not r['stopped']]
    counts['removed_by_stoplist'] = len(rows) - len(rows_kept)
    counts['removed_by_stoplist_top'] = collections.Counter(
        entities[r['eidx']]['label'] for r in rows if r['stopped']).most_common(15)
    log(f"list mentions: {len(rows)} before stoplist, {len(rows_kept)} after")

    for r in rows_kept:
        r['distinctive'] = (not multi[r['eidx']]) and r['stem'] >= DISTINCTIVE_STEM
    wanted = collections.defaultdict(set)
    for r in rows_kept:
        if not r['distinctive']:
            wanted[r['wid']].add(r['eidx'])
    desc_path = os.path.join(passage_dir, 'descriptions.jsonl')
    dh = description_hits(desc_path, wanted, exact, log=log) if os.path.exists(desc_path) else set()
    for r in rows_kept:
        r['ds'] = (r['wid'], r['eidx']) in dh
        r['conf'] = confidence_of(r['distinctive'], r['nb'], r['ds'])
    cc = collections.Counter(r['conf'] for r in rows_kept)
    counts['list_mentions'] = len(rows_kept)
    counts['list_mentions_by_confidence'] = dict(cc)
    counts['list_mentions_by_language'] = dict(collections.Counter(r['lang'] for r in rows_kept))
    unc = [r for r in rows_kept if not r['distinctive']]
    counts['uncertain_mentions'] = len(unc)
    counts['removed_by_neighbor_step'] = sum(1 for r in unc if not r['nb'])
    counts['removed_by_neighbor_or_description'] = sum(1 for r in unc if not (r['nb'] or r['ds']))
    counts['restored_by_description'] = counts['removed_by_neighbor_step'] - counts['removed_by_neighbor_or_description']

    # names source
    names_path = os.path.join(passage_dir, 'window_names.db')
    nm_ents, nm_rows, nm_meta = import_names(names_path, unit, None, log=log)
    counts['name_entities'] = len(nm_ents)
    counts['name_mentions'] = len(nm_rows)
    nk_df = {k: v['df'] for k, v in nm_ents.items()}

    # write
    tmp = out_path + '.tmp'
    if os.path.exists(tmp):
        os.remove(tmp)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    lab_count = collections.Counter(fold(e['label']) for e in entities)
    n_by_eidx = collections.Counter(r['eidx'] for r in rows_kept)
    dist_by = {}
    for r in rows_kept:
        dist_by[r['eidx']] = r['distinctive']
    for idx, e in enumerate(entities):
        eid = idx + 1
        pl = e['pleiades']
        nk = name_key_for(e, nk_df, names_key)
        hg = fold(e['label']) if lab_count[fold(e['label'])] > 1 else None
        db.execute('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (eid, e['entity_id'], e['type'], e['label'], 'list',
                    pl[0] if len(pl) == 1 else None, json.dumps(pl) if pl else None, None, hg, nk,
                    0 if multi[idx] else 1, n_by_eidx.get(idx, 0)))
        seen = set()
        for k in e['keys']:
            for lf in k['latin']:
                if (fold(lf), 'la') not in seen:
                    seen.add((fold(lf), 'la'))
                    db.execute('insert into variants values (?,?,?,?,?)', (eid, fold(lf), 'la', 'form', 'list'))
            g = fold(k['greek'])
            if (g, 'grc') not in seen:
                seen.add((g, 'grc'))
                db.execute('insert into variants values (?,?,?,?,?)', (eid, g, 'grc', 'form', 'list'))
            for ef in _english_forms(k.get('english')):
                if (fold(ef), 'en') not in seen:
                    seen.add((fold(ef), 'en'))
                    db.execute('insert into variants values (?,?,?,?,?)', (eid, fold(ef), 'en', 'form', 'list'))
    base = len(entities)
    nm_eid = {}
    n_by_name = collections.Counter(k for k, _, _ in nm_rows)
    for j, (k, v) in enumerate(sorted(nm_ents.items())):
        eid = base + j + 1
        nm_eid[k] = eid
        db.execute('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (eid, f'nm:{k}', 'name', v['label'], 'names', None, None, None, None, k, 0, n_by_name.get(k, 0)))
        for f, _c in v['forms'].most_common(5):
            db.execute('insert into variants values (?,?,?,?,?)', (eid, fold(f), '', 'form', 'names'))
    # windows
    wid_of = {}

    def wid_for(window_id):
        w = wid_of.get(window_id)
        if w is None:
            w = len(wid_of) + 1
            wid_of[window_id] = w
            lang, work, rs, re_ = wmeta[window_id]
            db.execute('insert into windows values (?,?,?,?,?,?)', (w, window_id, work, rs, re_, lang))
        return w

    db.executemany('insert into mention_rows values (?,?,?,?,?,?,?)',
                   ((r['eidx'] + 1, wid_for(r['wid']), r['form'], 1, int(r['nb']), int(r['ds']), r['conf'])
                    for r in rows_kept))
    db.executemany('insert into mention_rows values (?,?,?,?,?,?,?)',
                   ((nm_eid[k], wid_for(w), f, 1, 0, 0, 'name') for k, w, f in nm_rows if w in wmeta))
    counts['windows_with_mentions'] = len(wid_of)
    counts['windows_with_list_mentions'] = len({r['wid'] for r in rows_kept})
    counts['linked_name_keys'] = db.execute('select count(*) from entities where source="list" and name_key is not null').fetchone()[0]
    counts['built_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    counts['names_windows_meta'] = nm_meta.get('windows')
    counts['build_seconds'] = round(time.time() - t0)
    for k, v in counts.items():
        db.execute('insert into meta values (?,?)', (k, json.dumps(v) if isinstance(v, (dict, list)) else str(v)))
    db.executescript(INDEXES)
    db.commit()
    db.execute('vacuum')
    db.close()
    os.replace(tmp, out_path)
    log(json.dumps(counts, indent=1, default=str))
    return counts, rows, entities
