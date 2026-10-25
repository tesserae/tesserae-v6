"""People & Places mentions for works added after the store was built (2026-10-25).

The store (data/entity_index/entities.sqlite) is the result of a whole-corpus build and many hand
passes (model judgments of lemmas and windows, promotions, merges, carves, regroups, lower-case
drops). A fresh build would lose the hand passes, so this module adds the rows of NEW works to a COPY
of the live store and never rebuilds or edits a row that exists.

    scan_new_works()    candidate rows for the listed works, with the matchers the store was built with
    attribute_list()    list-entity candidates filtered by what the store already decided for the spelling
    attribute_names()   corpus-name rows filed under the entity the store files that spelling under
    write_rows()        windows, mention rows and the entities the new names need, into the copy

Nothing here calls a model or reads a key. See research notes in the pull request for the method.
"""
import collections
import json
import os
import re
import shutil
import sqlite3
import time

from backend import entity_index as ei

PART = re.compile(r'\.part\.[0-9_]+$')


def stem_of(work):
    """'plotinus.enneades.part.3' -> 'plotinus.enneades'."""
    return PART.sub('', work)


def work_of_window(window_id):
    return window_id.rsplit(':', 2)[0]


def new_unit(ids, stems):
    """The counted windows (entity_index.unit_windows) of the works whose stem is listed."""
    stems = set(stems)
    return {w for w in ei.unit_windows(ids) if stem_of(work_of_window(w)) in stems}


# ---------------------------------------------------------------- what the store already decided

def attested_list_forms(db):
    """{folded spelling: {eid: rows}} over the lemma-matcher rows of the store."""
    out = collections.defaultdict(dict)
    for fk, eid, n in db.execute("select form_key, eid, count(*) from mention_rows "
                                 "where matcher = 'lemma' and form_key is not null group by form_key, eid"):
        out[fk][eid] = n
    return out


def attested_name_forms(db):
    """{folded spelling: eid} the store files the spelling under (most rows of matcher 'names')."""
    best = {}
    for fk, eid, n in db.execute("select form_key, eid, count(*) from mention_rows "
                                 "where matcher = 'names' and form_key is not null group by form_key, eid"):
        cur = best.get(fk)
        if cur is None or n > cur[1] or (n == cur[1] and eid < cur[0]):
            best[fk] = (eid, n)
    return {fk: v[0] for fk, v in best.items()}



# ---------------------------------------------------------------- repairs found on review (2026-10-25)

# Spellings the live store files under another entity and that are a different name (the priest Achillas
# under the hero Achilles). Each becomes a new corpus name of its own for the NEW rows. Forms are folded.
OWN_ENTITIES = [
    {'tag': 'akhil:achillas', 'forms': ('achillas', 'achillam', 'achillae', 'αχιλλασ', 'αχιλλαν', 'αχιλλα')},
]

ROMAN = r'[IVXLCDM]+'
_AFTER_NUMBER = re.compile(r'\.\s*(?:\d+|' + ROMAN + r')\b')
_AFTER_PUNCT = re.compile(r'\.[,;:]')
_BEFORE_NUMBER = re.compile(r'(?:\b' + ROMAN + r'|\d+)\s+(?:(?:de|libro|lib)\s+)?$')
ABBREVIATION_SHARE = 0.8


_PATTERNS = {}


def abbreviation_hit(text, raw):
    """True when, at some occurrence of `raw` in `text`, the word is followed by a period and a number, a chapter
    number or a Roman numeral (Matth. XII, Exod. 17), or by a period and a comma or semicolon (Offic., Evang.,),
    or follows a number and a period (in II Polit., in VI Moral.)."""
    pat = _PATTERNS.get(raw)
    if pat is None:
        pat = _PATTERNS[raw] = re.compile(r'(?<!\w)' + re.escape(raw) + r'(?!\w)')
    for m in pat.finditer(text):
        after = text[m.end():m.end() + 14]
        if _AFTER_NUMBER.match(after) or _AFTER_PUNCT.match(after):
            return True
        if after.startswith('.') and _BEFORE_NUMBER.search(text[max(0, m.start() - 16):m.start()]):
            return True
    return False


def abbreviation_forms(rows, text_of, share=ABBREVIATION_SHARE):
    """rows: [(window id, raw form)]. A folded form is an abbreviation when in at least `share` of its rows the
    word is followed in the window by a period and a number or numeral (abbreviation_hit). Returns
    {folded form: (rows, rows that hit)} for those forms."""
    tally = collections.defaultdict(lambda: [0, 0])
    for wid, raw in rows:
        t = tally[ei.fold(raw)]
        t[0] += 1
        if abbreviation_hit(text_of(wid), raw):
            t[1] += 1
    return {f: tuple(t) for f, t in tally.items() if t[1] >= share * t[0]}


def enclitic_base(raw):
    """(folded base, enclitic) for a Latin spelling with -que, or -ve or -ne, else (None, None): the rule of
    entity_extras.without_enclitic that the search applies (#1114)."""
    from backend import entity_extras as ex
    return ex.without_enclitic(raw)


def attribute_list(cands, attested):
    """cands: [(eid, window id, raw form)]. Returns (rows, counts). A candidate stays when the store has
    never seen the spelling in a list row (the matcher's answer stands), or has seen it for that entity.
    A spelling the store files only under other entities is dropped, because a judgment or a hand pass
    took it away from this one. Rows of one (window, spelling) that keep several entities are flagged
    homonym."""
    by_tok = collections.defaultdict(list)
    for eid, wid, raw in cands:
        by_tok[(wid, ei.fold(raw), raw)].append(eid)
    rows = []
    counts = collections.Counter()
    for (wid, fk, raw), eids in by_tok.items():
        seen = attested.get(fk)
        base, enc = enclitic_base(raw)
        if enc and (enc == 'que' or (not seen and len(base) >= 4 and attested.get(base))):
            onto = attested.get(base)
            if onto:
                keep = [max(onto, key=lambda e: (onto[e], -e))]
                counts['enclitic_refiled_to_base_entity'] += 1
                rows.append((keep[0], wid, raw, 0, 'enclitic'))
            else:
                counts['enclitic_dropped_no_base_entity'] += 1
            continue
        if seen:
            keep = [e for e in eids if e in seen]
            counts['dropped_spelling_filed_elsewhere'] += len(eids) - len(keep)
            counts['kept_attested_spelling'] += len(keep)
        else:
            keep = list(eids)
            counts['kept_unseen_spelling'] += len(keep)
        hom = 1 if len(keep) > 1 else 0
        for e in keep:
            rows.append((e, wid, raw, hom, 'attested' if seen else 'unseen'))
    return rows, counts


def pick_name_entity(form, candidates, headings_of, case_form_of, prep):
    """Among entities that share a name key, the one a never-seen spelling belongs to: the only one, or the
    one (most rows) whose headings the spelling equals or is a case form of. None when none fits."""
    if len(candidates) == 1:
        return candidates[0][0]
    f = ei.fold(prep(form))
    fitting = []
    for eid, n in candidates:
        heads = headings_of(eid)
        if any(ei.fold(prep(h)) == f for h in heads) or case_form_of(prep(form), heads):
            fitting.append((n, -eid, eid))
    if not fitting:
        return None
    return max(fitting)[2]


def cluster_forms(forms, case_form_of, prep):
    """Group the spellings of one name key into names. forms: {raw spelling: count}. A spelling joins the
    first cluster (largest first) that holds a spelling it is a case form of, or that is a case form of it, or
    that folds to the same letters. Returns a list of clusters, each a list of raw spellings."""
    clusters = []
    for raw in sorted(forms, key=lambda f: (-forms[f], f)):
        for c in clusters:
            if any(ei.fold(prep(raw)) == ei.fold(prep(m)) or case_form_of(prep(raw), [prep(m)])
                   or case_form_of(prep(m), [prep(raw)]) for m in c):
                c.append(raw)
                break
        else:
            clusters.append([raw])
    return clusters


def attribute_names(name_rows, learned, dropped_forms, by_key, headings_of, case_form_of, prep):
    """name_rows: [(key, window id, raw form)]. Returns (placed, new_rows, new_names, counts).
    placed: [(eid, wid, raw, form_key)]. learned: {form_key: eid}. dropped_forms: spellings that occur in
    old windows of the names store and have no row there, so a hand pass dropped them. by_key:
    {name key: [(eid, rows)]} of the corpus-name and promoted entities.

    A spelling the store files under an entity goes there. Else it goes to the entity of its key (the
    only one, or the one whose headings it is a case form of). Else it is a name no existing row has: the
    spellings of such a key are grouped into names (cluster_forms), and each group becomes a new entity,
    tag 'KEY' when the key has no entity at all and only one group, else 'KEY:nN'. new_rows:
    [(tag, wid, raw, form_key, how)], new_names: {tag: Counter(raw)}."""
    placed, pending = [], []
    counts = collections.Counter()
    seen = set()
    for k, wid, raw in name_rows:
        fk = ei.fold(raw)
        eid = learned.get(fk)
        base, enc = enclitic_base(raw)
        if enc and (enc == 'que' or (eid is None and len(base) >= 4 and base in learned)):
            eid = learned.get(base)
            if eid is None:
                counts['enclitic_dropped_no_base_entity'] += 1
                continue
            how = 'enclitic_refiled_to_base_entity'
        elif eid is not None:
            how = 'learned'
        elif fk in dropped_forms:
            counts['left_out_dropped_by_hand_pass'] += 1
            continue
        else:
            cands = by_key.get(k)
            eid = pick_name_entity(raw, cands, headings_of, case_form_of, prep) if cands else None
            how = 'by_key' if eid is not None else ('new_carve' if cands else 'new_key')
        if eid is not None:
            if (eid, wid, fk) in seen:
                counts['duplicate_row'] += 1
                continue
            seen.add((eid, wid, fk))
            placed.append((eid, wid, raw, fk))
        else:
            pending.append((k, wid, raw, fk, how))
        counts[how] += 1
    by_k = collections.defaultdict(collections.Counter)
    for k, _w, raw, _fk, _h in pending:
        by_k[k][raw] += 1
    tag_of = {}
    for k, forms in by_k.items():
        clusters = cluster_forms(forms, case_form_of, prep)
        whole = len(clusters) == 1 and not by_key.get(k)
        for j, c in enumerate(clusters, 1):
            tag = k if whole else f'{k}:n{j}'
            for raw in c:
                tag_of[(k, raw)] = tag
    new_rows, new_names = [], collections.defaultdict(collections.Counter)
    seen_new = set()
    for k, wid, raw, fk, how in pending:
        tag = tag_of[(k, raw)]
        if (tag, wid, fk) in seen_new:
            counts['duplicate_row'] += 1
            counts[how] -= 1
            continue
        seen_new.add((tag, wid, fk))
        new_rows.append((tag, wid, raw, fk, how))
        new_names[tag][raw] += 1
    return placed, new_rows, new_names, counts


# ---------------------------------------------------------------- the writes

def write_rows(db, list_rows, placed_names, new_rows, new_names, wmeta, key_of_tag, labels_of, place_of=None):
    """Insert into an open copy of the store. list_rows: [(eid, wid, raw, homonym, how)], placed_names:
    [(eid, wid, raw, form_key)], new_rows: [(tag, wid, raw, form_key, how)], new_names: {tag: Counter},
    wmeta: {window id: (language, work, ref_start, ref_end)}. key_of_tag maps a tag to its name key,
    labels_of a Counter of forms to (label, display la, display grc). Returns the counts."""
    max_wid = db.execute('select coalesce(max(wid), 0) from windows').fetchone()[0]
    wid_of = {}

    def wid_for(window_id):
        w = wid_of.get(window_id)
        if w is None:
            r = db.execute('select wid from windows where window_id = ?', (window_id,)).fetchone()
            if r:
                w = r[0]
            else:
                nonlocal max_wid
                max_wid += 1
                w = max_wid
                lang, work, rs, re_ = wmeta[window_id]
                db.execute('insert into windows values (?,?,?,?,?,?)', (w, window_id, work, rs, re_, lang))
            wid_of[window_id] = w
        return w

    stats = {}
    # new entities
    max_eid = db.execute('select max(eid) from entities').fetchone()[0]
    tag_eid = {}
    new_entities = []
    n_by_tag = collections.Counter(t for t, _w, _r, _f, _h in new_rows)
    for tag in sorted(new_names):
        max_eid += 1
        tag_eid[tag] = max_eid
        forms = new_names[tag]
        label, la, grc = labels_of(forms)
        label = label or forms.most_common(1)[0][0]
        entity_id = 'nm:' + tag
        k = key_of_tag(tag)
        db.execute('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (max_eid, entity_id, 'name', label, 'names', None, None, None, None, k, 0, n_by_tag[tag]))
        for f, _c in forms.most_common(5):
            db.execute('insert into variants values (?,?,?,?,?)', (max_eid, ei.fold(f), '', 'form', 'names'))
        if db.execute("select 1 from sqlite_master where name = 'entity_labels'").fetchone():
            db.execute('insert into entity_labels(eid, display_label, display_label_la, display_label_grc, description) '
                       'values (?,?,?,?,?)', (max_eid, label, la, grc, None))
        new_entities.append((max_eid, entity_id, label, k, n_by_tag[tag], forms.most_common(3)))
    stats['new_entities'] = new_entities
    ins = ("insert into mention_rows(eid, wid, form, cap, nb, ds, confidence, matcher, homonym, line_ref, form_key) "
           "values (?,?,?,?,?,?,?,?,?,?,?)")
    db.executemany(ins, ((e, wid_for(w), raw, 1, 0, 0, 'lemma', 'lemma', hom, None, None)
                         for e, w, raw, hom, _h in list_rows))
    db.executemany(ins, ((e, wid_for(w), raw, 1, 0, 0, 'name', 'names', 0, None, None)
                         for e, w, raw, _fk in placed_names))
    db.executemany(ins, ((tag_eid[t], wid_for(w), raw, 1, 0, 0, 'name', 'names', 0, None, None)
                         for t, w, raw, _fk, _h in new_rows))
    stats['windows_added'] = len(wid_of)
    return stats


# ---------------------------------------------------------------- candidates (needs the passage index)

def read_decisions(paths):
    """{(lang, entity_id, lemma): 'drop'|'keep'|'other'} from stage 1d style lemma judgment files (the last
    answer for a pair wins), as scripts/entity_model_pass.py load_decisions reads them."""
    last = {}
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    last[(r['lang'], r['entity_id'], r['lemma'])] = r.get('answer')
    mapping = {'yes': 'keep', 'demonym': 'drop', 'common': 'drop', 'other': 'other'}
    return {k: mapping[v] for k, v in last.items() if v in mapping}


def scan_new_works(keys, passage_dir, stems, decision_paths, token_blocks_path=None, log=print):
    """Candidates for the listed works with the lemma matcher the store was built with.

    Returns {'list': [(entity id, window id, raw form)], 'names': [(key, window id, raw form)],
    'wmeta': {window id: (language, work, ref_start, ref_end)}, 'unit_new': int, 'unit_all': int}.
    The capitalization threshold of the matcher reads type counts over every counted window, new works
    included, so that each token of a new window has a lemma."""
    from backend import entity_lemma as el
    entities, _review = ei.merge_list_entities(keys)
    ids = json.load(open(os.path.join(passage_dir, 'ids.json')))
    unit_all = ei.unit_windows(ids)
    unit_new = {w for w in unit_all if stem_of(work_of_window(w)) in set(stems)}
    del ids
    texts = sqlite3.connect(f"file:{os.path.join(passage_dir, 'window_texts.db')}?mode=ro", uri=True)
    types = el.count_types(texts, unit_all, log=log)
    resolver = el.Resolver(log=log)
    prep = el.prepare_lemmas(entities, types, resolver, log=log)
    decisions = read_decisions(decision_paths)
    blocks = set()
    if token_blocks_path and os.path.exists(token_blocks_path):
        blocks = {tuple(x) for x in json.load(open(token_blocks_path, encoding='utf-8'))}
    tok2ents, info = el.assemble_matcher(entities, types, prep, decisions=decisions, token_blocks=blocks, log=log)
    rows, wmeta, tally = el.scan_windows_lemma(texts, unit_new, tok2ents, log=log, amb_tokens=info['amb_tokens'],
                                               answers={})
    texts.close()
    lst = [(entities[r['eidx']]['entity_id'], r['wid'], r['form']) for r in rows]
    names = []
    seen = set()
    c = sqlite3.connect(f"file:{os.path.join(passage_dir, 'window_names.db')}?mode=ro", uri=True)
    for wid, k, form in c.execute('select id, k, form from window_names'):
        if wid in unit_new and k and (wid, k) not in seen:
            seen.add((wid, k))
            names.append((k, wid, form))
    c.close()
    log(f'candidates: {len(lst)} list, {len(names)} names, {len(unit_new)} of {len(unit_all)} counted windows')
    return {'list': lst, 'names': names, 'wmeta': wmeta, 'unit_new': len(unit_new), 'unit_all': len(unit_all),
            'tally': dict(tally), 'decisions': len(decisions), 'blocks': len(blocks)}


def old_name_forms_seen(passage_dir, unit_old_pred, wanted):
    """Spellings among `wanted` (folded) that occur in window_names.db rows of counted windows that are
    not in the new works. Used to tell a spelling a hand pass dropped from one nobody has seen."""
    ids = json.load(open(os.path.join(passage_dir, 'ids.json')))
    unit = ei.unit_windows(ids)
    del ids
    c = sqlite3.connect(f"file:{os.path.join(passage_dir, 'window_names.db')}?mode=ro", uri=True)
    seen = set()
    for wid, _k, form in c.execute('select id, k, form from window_names'):
        if wid in unit and not unit_old_pred(wid):
            f = ei.fold(form)
            if f in wanted:
                seen.add(f)
    c.close()
    return seen


def file_candidates(cands, store_path, passage_dir, stems, log=print):
    """Turn the candidates into attributed rows against the (read only) store. Returns a dict with
    list_rows, placed_names, new_rows, new_names and counts."""
    from backend import entity_mergeback as mb
    from backend import entity_regroup as rg
    db = sqlite3.connect(f'file:{store_path}?mode=ro&immutable=1', uri=True)
    # a work that already has windows in the store was built with it: its rows stay as they are
    built = {stem_of(w) for (w,) in db.execute('select distinct work from windows')} & set(stems)
    if built:
        gone = {w for w in cands['wmeta'] if stem_of(work_of_window(w)) in built}
        cands = dict(cands, list=[c for c in cands['list'] if c[1] not in gone],
                     names=[c for c in cands['names'] if c[1] not in gone],
                     wmeta={w: m for w, m in cands['wmeta'].items() if w not in gone})
    # repair 2: book and work abbreviations (Matth. XII, in II Polit.) are not names, found by the data
    tx = sqlite3.connect(f"file:{os.path.join(passage_dir, 'window_texts.db')}?mode=ro", uri=True)
    texts = {}

    def text_of(wid):
        t = texts.get(wid)
        if t is None:
            r = tx.execute('select text from window_texts where id = ?', (wid,)).fetchone()
            t = texts[wid] = r[0] if r else ''
        return t

    allrows = [(c[1], c[2]) for c in cands['list']] + [(c[1], c[2]) for c in cands['names']]
    abbr = abbreviation_forms(allrows, text_of)
    tx.close()
    abbr_dropped = collections.Counter()
    for kind in ('list', 'names'):
        keep = []
        for c in cands[kind]:
            f = ei.fold(c[2])
            if f in abbr:
                abbr_dropped[(kind, f)] += 1
            else:
                keep.append(c)
        cands = dict(cands, **{kind: keep})
    # repair 3: spellings that are a different name from the entity the store files them under
    own_forms = {f: o['tag'] for o in OWN_ENTITIES for f in o['forms']}
    forced, own_names = [], collections.defaultdict(collections.Counter)
    for kind in ('list', 'names'):
        keep, seen_own = [], set()
        for c in cands[kind]:
            f = ei.fold(c[2])
            if f in own_forms:
                tag = own_forms[f]
                if (tag, c[1], f) not in seen_own and (tag, c[1], f) not in {(x[0], x[1], x[3]) for x in forced if x[1] == c[1]}:
                    forced.append((tag, c[1], c[2], f, 'own_entity'))
                    own_names[tag][c[2]] += 1
                seen_own.add((tag, c[1], f))
            else:
                keep.append(c)
        cands = dict(cands, **{kind: keep})
    eid_by_id = {eid_s: eid for eid, eid_s in db.execute("select eid, entity_id from entities where source = 'list'")}
    unknown = collections.Counter()
    mapped = []
    for ent_id, wid, raw in cands['list']:
        eid = eid_by_id.get(ent_id)
        if eid is None:
            unknown[ent_id] += 1
        else:
            mapped.append((eid, wid, raw))
    list_rows, lcounts = attribute_list(mapped, attested_list_forms(db))
    lcounts['candidates'] = len(mapped)
    lcounts['unknown_entity_ids'] = sum(unknown.values())
    learned = attested_name_forms(db)
    wanted = {ei.fold(f) for _k, _w, f in cands['names']} - set(learned)
    stemset = set(stems)
    seen_old = old_name_forms_seen(passage_dir, lambda w: stem_of(work_of_window(w)) in stemset, wanted)
    dropped = seen_old
    by_key = collections.defaultdict(list)
    for eid, k, n in db.execute("select e.eid, e.name_key, (select count(*) from mention_rows where eid = e.eid) "
                                "from entities e where e.source in ('names', 'promoted') and e.name_key is not null"):
        by_key[k].append((eid, n))
    heads_cache = {}

    def headings_of(eid):
        h = heads_cache.get(eid)
        if h is None:
            h = heads_cache[eid] = rg.headings(db, eid)
        return h

    placed, new_rows, new_names, ncounts = attribute_names(cands['names'], learned, dropped, dict(by_key), headings_of,
                                                           mb.case_form_of, rg.prep)
    db.close()
    new_rows = new_rows + forced
    for tag, forms in own_names.items():
        new_names[tag].update(forms)
    return {'abbreviations': {f: {'rows': n, 'hit': h} for f, (n, h) in abbr.items()},
            'abbreviation_rows_dropped': {f'{k}:{f}': n for (k, f), n in abbr_dropped.items()},
            'own_entity_rows': sum(len(v) for v in own_names.values()),
            'list_rows': list_rows, 'placed_names': placed, 'new_rows': new_rows, 'new_names': new_names,
            'list_counts': dict(lcounts), 'name_counts': dict(ncounts), 'skipped_built_works': sorted(built),
            'wmeta': cands['wmeta']}


# ---------------------------------------------------------------- the copy

def entities_digest(db, max_eid=None):
    """sha256 over every column of the entities rows (eid order), up to max_eid when given."""
    import hashlib
    h = hashlib.sha256()
    if max_eid is not None:
        rows = db.execute('select * from entities where eid <= ? order by eid', (max_eid,))
    else:
        rows = db.execute('select * from entities order by eid')
    for r in rows:
        h.update(repr(r).encode())
    return h.hexdigest()


def table_digest(db, table, order):
    import hashlib
    h = hashlib.sha256()
    for r in db.execute(f'select * from {table} order by {order}'):  # nosec B608
        h.update(repr(r).encode())
    return h.hexdigest()


def add_works(store, out, filed, wmeta, passage_dir, fingerprint_now, report, log=print):
    """Copy `store` to `out` and add the filed rows. `filed` is file_candidates()'s result, `wmeta` the
    window metadata of the new windows, `fingerprint_now` entity_index.fingerprint() of the passage index.
    Refuses an out under /var/www or equal to store. Returns the report dict (also written to `report`)."""
    from backend import entity_extras as ex
    from backend import entity_promote as pr
    if os.path.realpath(out).startswith('/var/www') or os.path.realpath(out) == os.path.realpath(store):
        raise SystemExit('refusing: --out must be a new file outside /var/www')
    t0 = time.time()
    shutil.copyfile(store, out)
    db = sqlite3.connect(out)
    old_max_eid = db.execute('select max(eid) from entities').fetchone()[0]
    old_digest = entities_digest(db)
    old_rows = db.execute('select count(*) from mention_rows').fetchone()[0]
    old_rowid = db.execute('select coalesce(max(rowid), 0) from mention_rows').fetchone()[0]
    stats = write_rows(db, filed['list_rows'], filed['placed_names'], filed['new_rows'], filed['new_names'], wmeta,
                       lambda tag: tag.split(':')[0], pr.display_labels)
    # the corpus names that are new get search names from their spellings, as add_form_search_names does
    sn = 0
    for eid, form in db.execute("select v.eid, v.form from variants v join entities e on e.eid = v.eid "
                                "where e.eid > ? and e.source = 'names'", (old_max_eid,)).fetchall():
        f = ei.fold(form)
        if f:
            db.execute('insert into search_names values (?,?,?)', (eid, ex.form_stem(f), 'form'))
            sn += 1
    for k in ('ids_total', 'unit_windows', 'names_windows_meta'):
        db.execute('delete from meta where key = ?', (k,))
        db.execute('insert into meta values (?,?)', (k, str(fingerprint_now[k])))
    db.commit()
    db.close()
    works = {m[1] for m in wmeta.values()}
    stats['line_refs'] = ex.add_line_refs(out, os.path.join(passage_dir, 'window_texts.db'), log=log, works=works)
    ex.write_catalog(out, log=log)
    ex.write_form_index(out, log=log)
    db = sqlite3.connect(out)
    new_rows = db.execute('select count(*) from mention_rows').fetchone()[0] - old_rows
    stats.update({'search_names_added': sn, 'mention_rows_added': new_rows, 'old_rowid_max': old_rowid,
                  'old_entities_digest': old_digest,
                  'entities_digest_after_for_old_rows': entities_digest(db, old_max_eid),
                  'entities_before': old_max_eid})
    db.execute("delete from meta where key = 'new_works_2026_10_25'")
    db.execute("insert into meta values ('new_works_2026_10_25', ?)", (json.dumps(
        {'rows': new_rows, 'new_entities': len(stats['new_entities']), 'work_parts': len(works)}),))
    db.commit()
    db.close()
    stats['seconds'] = round(time.time() - t0)
    if report:
        json.dump(stats, open(report, 'w'), ensure_ascii=False, indent=1, default=list)
    return stats
