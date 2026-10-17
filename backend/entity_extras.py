"""Entity mentions, stage 2b: corpus names attached to list entities, one row per matched line,
and the inscriptions and papyri that name an entity.

Three pieces, all read-only against the passage index and the documents index:

    NameIndex, attach_keys, attached_names   corpus names (store source 'names') that belong to a
                                             list entity: a name that starts with the entity's
                                             label stem or with one of its name forms. Rusellae
                                             owns the corpus name Rusellanum this way. Used by the
                                             routes and by the documents build, so the two agree.
    add_line_refs                            adds line_ref and form_key to mention_rows: the line of
                                             the window that holds the matched token, so two
                                             overlapping windows that hold one line count once.
    build_document_mentions                  the document_mentions table, see its docstring.
"""
import bisect
import json
import re
import sqlite3
import time

from backend import entity_index as ei
from backend.entity_lemma_audit import adjective_form, token_language

STEM_MIN = 4


class NameIndex:
    """Folded strings -> corpus-name entity ids, answering prefix and exact lookups."""

    def __init__(self, items):
        pairs = sorted({(s, eid) for eid, strings in items for s in strings if s})
        self.keys = [p[0] for p in pairs]
        self.eids = [p[1] for p in pairs]

    def prefix(self, p):
        lo = bisect.bisect_left(self.keys, p)
        hi = bisect.bisect_left(self.keys, p + '￿')
        return set(self.eids[lo:hi])

    def prefix_pairs(self, p):
        lo = bisect.bisect_left(self.keys, p)
        hi = bisect.bisect_left(self.keys, p + '\uffff')
        return list(zip(self.keys[lo:hi], self.eids[lo:hi]))

    def exact(self, s):
        lo = bisect.bisect_left(self.keys, s)
        hi = bisect.bisect_right(self.keys, s)
        return set(self.eids[lo:hi])


FIRST_DECLENSION = ('a', 'ae', 'am', 'as', 'arum', 'is')


def case_variants(form, ends):
    """The form and the same stem with each closed case ending, by the matcher's own rule
    (entity_index.variants, four letters of stem). One addition: a four-letter Latin form in -a
    (Roma, Cyme) also takes the first-declension endings, so that Roma gives Romae and Romam. A
    shorter stem for every form was tried and let hero take Herem."""
    out = ei.variants(form, ends)[0]
    if len(form) == 4 and form.endswith('a') and ends is ei.LA_END:
        out |= {form[:-1] + e for e in FIRST_DECLENSION}
    return out


def _ends_for(s):
    return ei.GR_END if token_language(s) == 'grc' else ei.LA_END


def name_forms_of(label_key, forms):
    """Every folded string a list entity's name can take: its label words and name forms, each
    with the case endings the matcher allows (entity_index.variants)."""
    base = {part for part in (label_key or '').split() if len(part) >= 3}
    for f in forms:
        ff = ei.fold(f)
        if len(ff) >= 3:
            base.add(ff)
    out = set()
    for s in base:
        out |= case_variants(s, _ends_for(s))
    return out


def place_stems(label_key, forms):
    """Stems of a place's name, four letters at least: each label word with its last two letters
    removed, and each name form with a case ending removed."""
    stems = set()
    for part in (label_key or '').split():
        if len(part) >= STEM_MIN:
            stems.add(part[:max(STEM_MIN, len(part) - 2)])
    for f in forms:
        ff = ei.fold(f)
        st = ei.strip_end(ff, _ends_for(ff), STEM_MIN)
        if len(st) >= STEM_MIN:
            stems.add(st)
    return stems


def attached_names(index, label_key, forms, excluded=frozenset(), is_place=False):
    """Corpus-name entity ids that belong to a list entity, and nothing else. (a) A name equal to
    one of the entity's name forms or label words, with a case ending the matcher allows. (b) For
    a place, a name that is the place's stem plus an adjective suffix (backend/
    entity_lemma_suffixes.json, as entity_lemma_audit.adjective_form reads it). `excluded` are
    names that are the list entity's own forms, which the search already shows as the entity."""
    out = set()
    for v in name_forms_of(label_key, forms):
        out |= index.exact(v)
    if is_place:
        for st in place_stems(label_key, forms):
            for string, nid in index.prefix_pairs(st):
                if nid not in out and adjective_form(string):
                    out.add(nid)
    return out - set(excluded)


# ---------------------------------------------------------------- line_ref

_TOKEN = re.compile(r'[^\W\d_]+', re.UNICODE)


def add_line_refs(store_path, texts_db, log=print):
    """Add line_ref (the stored ref of the first line of the window that holds the matched token)
    and form_key (the folded token) to mention_rows. A mention whose token is found in no line of
    its window keeps a NULL line_ref and counts as its own line. Returns counts."""
    from backend.utils import normalize_ref
    t0 = time.time()
    db = sqlite3.connect(store_path)
    cols = {r[1] for r in db.execute('pragma table_info(mention_rows)')}
    for col in ('line_ref', 'form_key'):
        if col not in cols:
            db.execute(f'alter table mention_rows add column {col} TEXT')
    tx = sqlite3.connect(f'file:{texts_db}?mode=ro', uri=True)
    works = [r[0] for r in db.execute('select distinct work from windows')]
    found = missing = 0
    for n, work in enumerate(works):
        lines = tx.execute('select ord, ref, text from lines where work = ? order by ord', (work,)).fetchall()
        at = {}
        for pos, (o, ref, _t) in enumerate(lines):
            at.setdefault(ref, pos)
        for pos, (o, ref, _t) in enumerate(lines):
            at.setdefault(normalize_ref(ref), pos)
        toks = {}

        def tokens_of(pos, toks=toks, lines=lines):
            t = toks.get(pos)
            if t is None:
                folded = ei.fold(lines[pos][2])
                t = toks[pos] = (set(_TOKEN.findall(folded)), folded)
            return t

        updates = []
        for rowid, form, rs, re_ in db.execute(
                'select m.rowid, m.form, w.ref_start, w.ref_end from mention_rows m '
                'join windows w on w.wid = m.wid where w.work = ?', (work,)):
            key = ei.fold(form)
            i = at.get(rs, at.get(normalize_ref(rs)))
            j = at.get(re_, at.get(normalize_ref(re_), i))
            line = None
            if i is not None:
                if j is None or j < i:
                    j = i
                j = min(j, i + 200)
                for pos in range(i, j + 1):
                    ts, folded = tokens_of(pos)
                    if key in ts or (' ' in key and key in folded):
                        line = lines[pos][1]
                        break
            updates.append((line, key, rowid))
            if line is None:
                missing += 1
            else:
                found += 1
        db.executemany('update mention_rows set line_ref = ?, form_key = ? where rowid = ?', updates)
        if n % 200 == 0:
            db.commit()
            log(f'  line refs: {n}/{len(works)} works, {found} mentions placed')
    db.execute('create index if not exists ix_mr_line on mention_rows(eid, line_ref)')
    stats = {'placed': found, 'unplaced': missing}
    drop_catalog(db)
    db.execute("delete from meta where key in ('line_refs', 'line_refs_seconds')")
    db.execute("insert into meta values ('line_refs', ?)", (json.dumps(stats),))
    db.execute("insert into meta values ('line_refs_seconds', ?)", (str(round(time.time() - t0)),))
    db.commit()
    db.close()
    tx.close()
    return stats


LINE_GROUP_SQL = "coalesce(m.line_ref, '#' || m.wid) || '|' || coalesce(m.form_key, lower(m.form))"


def line_counts(db):
    """{(eid, language): number of distinct (work, line, form) groups} and the same by windows."""
    if 'line_ref' in {r[1] for r in db.execute('pragma table_info(mention_rows)')}:
        key = LINE_GROUP_SQL
    else:
        key = "'#' || m.wid"
    lines = {}
    for eid, lang, n in db.execute(
            f"select eid, language, count(*) from (select distinct m.eid eid, w.language language, w.work, {key} k "  # nosec B608
            "from mention_rows m join windows w on w.wid = m.wid) group by eid, language"):
        lines[(eid, lang)] = n
    return lines


# ---------------------------------------------------------------- catalog

TYPE_OUT = {'place': 'place', 'person': 'person', 'deity': 'deity'}
LANG_ORDER = ('la', 'grc', 'en')


def build_catalog(db):
    """One dict per entity (list entities and corpus names) with everything the routes need to
    search and show it: label, type, identifiers, name forms, mention counts by language (lines),
    shared-name facts, whether a corpus name is a list entity's own form, and for a list entity
    the corpus names that belong to it. JSON-safe, so it can be stored (write_catalog)."""
    ents, names = {}, {}
    for eid, entity_id, typ, label, pid, cands, group in db.execute(
            "select eid, entity_id, type, label, pleiades_id, pleiades_candidates, homonym_group "
            "from entities where source = 'list'"):
        try:
            pl = json.loads(cands) if cands else ([pid] if pid else [])
        except ValueError:
            pl = [pid] if pid else []
        ents[eid] = {'eid': eid, 'id': entity_id, 'label': label, 'type': TYPE_OUT.get(typ, 'other'),
                     'list_type': typ, 'source': 'list', 'pleiades': [str(x) for x in pl], 'forms': [],
                     'merged_ids': [], 'counts': {}, 'label_key': ei.label_key(label), 'homonym_mentions': 0}
    for eid, form in db.execute("select eid, form from variants where source = 'list'"):
        if eid in ents:
            ents[eid]['forms'].append(form)
    for eid, alias in db.execute("select eid, alias_id from entity_aliases"):
        if eid in ents:
            ents[eid]['merged_ids'].append(alias)
    for eid, entity_id, label in db.execute("select eid, entity_id, label from entities where source = 'names'"):
        f = ei.fold(label)
        names[eid] = {'eid': eid, 'id': entity_id, 'label': label, 'type': 'name', 'source': 'corpus',
                      'pleiades': [], 'forms': [], 'merged_ids': [], 'counts': {}, 'label_key': f,
                      'folded_label': f, 'homonym_mentions': 0, 'shared_label_with': []}
    for eid, form in db.execute("select eid, form from variants where source = 'names'"):
        if eid in names:
            names[eid]['forms'].append(ei.fold(form))
    for (eid, lang), n in line_counts(db).items():
        e = ents.get(eid) or names.get(eid)
        if e is not None:
            e['counts'][lang] = n
    for eid, hom in db.execute("select eid, count(*) from mention_rows where homonym = 1 group by eid"):
        if eid in ents:
            ents[eid]['homonym_mentions'] += hom or 0
    by_key = {}
    for e in ents.values():
        if e['label_key']:
            by_key.setdefault(e['label_key'], []).append(e)
    list_strings = set()
    for e in ents.values():
        e['shared_label_with'] = [o['label'] for o in by_key.get(e['label_key'], ()) if o is not e]
        e['total'] = sum(e['counts'].values())
        e['folded_label'] = ei.fold(e['label'])
        list_strings |= {e['folded_label'], e['label_key']} | {ei.fold(f) for f in e['forms']}
    list_strings.discard('')
    for n in names.values():
        n['total'] = sum(n['counts'].values())
        n['duplicate'] = bool(({n['folded_label']} | set(n['forms'])) & list_strings)
    index = NameIndex([(n['eid'], {n['folded_label']} | set(n['forms'])) for n in names.values()])
    dup = {n['eid'] for n in names.values() if n['duplicate']}
    for e in ents.values():
        out = []
        for nid in attached_names(index, e['label_key'], e['forms'], dup, e['list_type'] == 'place'):
            n = names[nid]
            if n['total'] == 0:
                continue
            out.append({'id': n['id'], 'label': n['label'],
                        'mention_counts': {lg: n['counts'][lg] for lg in LANG_ORDER if lg in n['counts']},
                        'mentions_total': n['total'],
                        'adjective': e['list_type'] == 'place' and adjective_form(n['label'])})
        out.sort(key=lambda r: (-r['mentions_total'], r['label']))
        e['corpus_names'] = out[:30]
    return list(ents.values()) + list(names.values())


def write_catalog(store_path, log=print):
    """Store the catalog as the table entity_catalog (one JSON row per entity), so a worker reads
    it in one select instead of building it from the whole store on its first request."""
    t0 = time.time()
    db = sqlite3.connect(store_path)
    rows = build_catalog(db)
    db.executescript('DROP TABLE IF EXISTS entity_catalog; CREATE TABLE entity_catalog (eid INTEGER PRIMARY KEY, data TEXT);')
    db.executemany('insert into entity_catalog values (?, ?)', [(r['eid'], json.dumps(r, ensure_ascii=False)) for r in rows])
    db.execute("delete from meta where key = 'catalog_built'")
    db.execute("insert into meta values ('catalog_built', ?)", (time.strftime('%Y-%m-%d %H:%M:%S'),))
    db.commit()
    db.close()
    log(f'catalog: {len(rows)} entities, {time.time() - t0:.0f}s')
    return len(rows)


def drop_catalog(db):
    """A step that changes counts makes the stored catalog stale, so it is dropped (the routes
    then build it in memory, slowly, until write_catalog runs again)."""
    db.execute('DROP TABLE IF EXISTS entity_catalog')
    db.execute("delete from meta where key = 'catalog_built'")


# ---------------------------------------------------------------- documents

def formula_forms(formula_dir):
    """{'la': set, 'grc': set} of folded words in the documents collection's formula lists."""
    import os
    out = {}
    for lang in ('la', 'grc'):
        words = set()
        path = os.path.join(formula_dir, f'formula_words_{lang}.txt')
        if os.path.exists(path):
            for line in open(path, encoding='utf-8'):
                line = line.strip()
                if line and not line.startswith('#'):
                    words.add(ei.fold(line))
        out[lang] = words
    return out


def common_forms(passage_dir, log=print, cache_path=None):
    """{'la': set, 'grc': set} of folded forms that are mostly lower case in the literary
    corpus (the stage 1b measure: the share of inner occurrences that are lower case is above
    one half). Counts the counted windows of the passage index; cached as JSON when a path is
    given, because the count takes minutes."""
    import os
    from backend import entity_lemma as el
    if cache_path and os.path.exists(cache_path):
        data = json.load(open(cache_path))
        return {lg: set(data[lg]) for lg in ('la', 'grc')}
    ids = json.load(open(os.path.join(passage_dir, 'ids.json')))
    unit = ei.unit_windows(ids)
    del ids
    tx = sqlite3.connect(f"file:{os.path.join(passage_dir, 'window_texts.db')}?mode=ro", uri=True)
    types = el.count_types(tx, unit, log)
    tx.close()
    out = {}
    for lg in ('la', 'grc'):
        out[lg] = {f for f, v in types[lg].items() if v[0] and ((v[3] / v[2]) if v[2] else (v[1] / v[0])) < 0.5}
    if cache_path:
        json.dump({lg: sorted(v) for lg, v in out.items()}, open(cache_path, 'w'))
    return out


DOC_SCHEMA = '''
DROP TABLE IF EXISTS document_mentions;
CREATE TABLE document_mentions (eid INTEGER, doc_id TEXT, language TEXT, form TEXT, kind TEXT, adjective INTEGER);
'''
DOC_INDEX = 'CREATE INDEX ix_dm_eid ON document_mentions(eid, language)'
PRIORITY = {'form': 0, 'corpus_name': 1, 'adjective_stem': 2}


def _load_entities(db):
    ents = {}
    for eid, entity_id, typ, label, source in db.execute('select eid, entity_id, type, label, source from entities'):
        ents[eid] = {'eid': eid, 'id': entity_id, 'type': typ, 'label': label, 'source': source,
                     'forms': {'la': set(), 'grc': set(), 'en': set(), '': set()}}
    for eid, form, lang in db.execute('select eid, form, language from variants'):
        if eid in ents:
            ents[eid]['forms'].setdefault(lang or '', set()).add(form)
    return ents


def _name_index_and_excluded(ents):
    names = [(e['eid'], {ei.fold(e['label'])} | {ei.fold(f) for f in e['forms']['']}) for e in ents.values()
             if e['source'] == 'names']
    index = NameIndex(names)
    own = set()
    for e in ents.values():
        if e['source'] == 'list':
            own.add(ei.fold(e['label']))
            own.add(ei.label_key(e['label']))
            for lg in ('la', 'grc', 'en'):
                own |= {ei.fold(f) for f in e['forms'][lg]}
    own.discard('')
    duplicate_names = {eid for eid, strings in names if strings & own}
    return index, {eid: strings for eid, strings in names}, duplicate_names


def attached_for(e, index, name_strings, duplicate_names):
    forms = set()
    for lg in ('la', 'grc', 'en'):
        forms |= e['forms'][lg]
    return attached_names(index, ei.label_key(e['label']), forms, duplicate_names, e['type'] == 'place')


def build_maps(ents, log=print):
    """Per document language: exact[token] -> [(eid, kind, adjective)], and the place stems
    stems[first four letters] -> [(stem, eid)] for the adjective rule."""
    index, name_strings, duplicate_names = _name_index_and_excluded(ents)
    exact = {'la': {}, 'grc': {}}
    stems = {'la': {}, 'grc': {}}

    def add(lang, tok, eid, kind, adj):
        lst = exact[lang].setdefault(tok, [])
        if not any(x[0] == eid for x in lst):
            lst.append((eid, kind, adj))

    n_attached = 0
    for e in ents.values():
        if e['source'] == 'list':
            for lg, ends, target in (('la', ei.LA_END, 'la'), ('en', ei.LA_END, 'la'), ('grc', ei.GR_END, 'grc')):
                for f in e['forms'][lg]:
                    ff = ei.fold(f)
                    if not ff:
                        continue
                    for v in case_variants(ff, ends):
                        add(target, v, e['eid'], 'form', False)
            att = attached_for(e, index, name_strings, duplicate_names)
            n_attached += len(att)
            for nid in att:
                for s in name_strings[nid]:
                    add(token_language(s), s, e['eid'], 'corpus_name', e['type'] == 'place' and adjective_form(s))
            if e['type'] == 'place':
                allf = set()
                for lg in ('la', 'grc', 'en'):
                    allf |= {ei.fold(f) for f in e['forms'][lg]}
                for st in place_stems(ei.label_key(e['label']), allf):
                    stems[token_language(st)].setdefault(st[:STEM_MIN], []).append((st, e['eid']))
        elif e['eid'] not in duplicate_names:
            for s in name_strings[e['eid']]:
                if len(s) >= 3:
                    add(token_language(s), s, e['eid'], 'form', False)
    log(f'maps: la {len(exact["la"])} forms, grc {len(exact["grc"])} forms, {n_attached} attached corpus names')
    return exact, stems, n_attached


def documents_fingerprint(documents_dir):
    import os
    out = {}
    for lang in ('la', 'grc'):
        path = os.path.join(documents_dir, f'{lang}_documents_index.db')
        out[lang] = os.path.getsize(path) if os.path.exists(path) else None
    return json.dumps(out)


def extras_problems(store_path, documents_dir=None):
    """Problems with the stage 2b tables: line refs not built, document mentions not built, or built
    against a documents index of another size."""
    problems = []
    db = sqlite3.connect(f'file:{store_path}?mode=ro', uri=True)
    meta = dict(db.execute('select key, value from meta'))
    db.close()
    if 'line_refs' not in meta:
        problems.append('line_ref not built: run scripts/build_entity_index.py --lines')
    if 'catalog_built' not in meta:
        problems.append('catalog not built (the routes build it slowly on first use): run scripts/build_entity_index.py --catalog')
    if 'document_mentions' not in meta:
        problems.append('document_mentions not built: run scripts/build_entity_index.py --documents')
    elif documents_dir and meta.get('documents_fingerprint') != documents_fingerprint(documents_dir):
        problems.append('document_mentions was built against a different documents index: '
                        f'{meta.get("documents_fingerprint")} then, {documents_fingerprint(documents_dir)} now')
    return problems


def build_document_mentions(store_path, documents_dir, log=print, max_form_documents=0, excluded_forms=None):
    """Fill document_mentions in the store: for every list entity and every corpus name, the
    documents whose text holds one of its forms as a whole token, case and accent folded.
    Forms are the entity's name forms with the case endings, the forms of the corpus names
    attached to it, and (places only) any token that starts with one of the place's stems and
    reads as a demonym or an adjective by the suffix rule. One row per entity and document, the
    best kind winning (form, then corpus name, then adjective). Nothing of the document text is
    stored. excluded_forms ({'la': set, 'grc': set} of folded words, see formula_forms and
    common_forms) leaves out every token in the set: documentary formulas and words that are
    mostly lower case in the literary corpus. The counts of the documents each excluded word would
    have matched go in the returned counts. max_form_documents, when above zero, drops every row of a form that appears in more
    documents of a language than that number (stock words such as dis and manibus); the default
    keeps them all. The documents index has no token table (its postings hold lemmas), so the build reads
    every line's token list once per language. Returns the counts."""
    import os
    t0 = time.time()
    db = sqlite3.connect(store_path)
    ents = _load_entities(db)
    exact, stems, n_attached = build_maps(ents, log)
    db.executescript(DOC_SCHEMA)
    counts = {}
    for lang in ('la', 'grc'):
        path = os.path.join(documents_dir, f'{lang}_documents_index.db')
        if not os.path.exists(path):
            log(f'  no documents index for {lang}')
            continue
        src = sqlite3.connect(f'file:{path}?mode=ro&immutable=1', uri=True)
        cache = {}
        ex, st = exact[lang], stems[lang]
        skip = (excluded_forms or {}).get(lang, set())
        skipped_docs = {}
        doc_skipped = set()

        def matches(tok, cache=cache, ex=ex, st=st, skip=skip, skipped_docs=skipped_docs, lang=lang):
            hit = cache.get(tok)
            if hit is not None:
                return hit
            f = ei.fold(tok)
            if f in skip:
                cache[tok] = res = []
                if ex.get(f) or (f[:STEM_MIN] in st and adjective_form(f, lang)):
                    skipped_docs.setdefault(f, 0)
                return res
            res = list(ex.get(f, ()))
            if f[:STEM_MIN] in st and adjective_form(f, lang):
                have = {x[0] for x in res}
                for stem, eid in st[f[:STEM_MIN]]:
                    if f.startswith(stem) and eid not in have:
                        res.append((eid, 'adjective_stem', True))
                        have.add(eid)
            cache[tok] = res
            return res

        rows, cur_doc, cur = [], None, {}
        n_docs = 0

        def flush(cur_doc, cur, rows, lang=lang):
            for eid, (pr, form, kind, adj) in cur.items():
                rows.append((eid, cur_doc, lang, form, kind, 1 if adj else 0))

        for ref, tokens in src.execute('select ref, tokens from lines order by text_id, rowid'):
            doc = ref.split(' ', 1)[0]
            if doc != cur_doc:
                if cur_doc is not None:
                    flush(cur_doc, cur, rows)
                    if len(rows) >= 50000:
                        db.executemany('insert into document_mentions values (?,?,?,?,?,?)', rows)
                        rows = []
                cur_doc, cur = doc, {}
                doc_skipped.clear()
                n_docs += 1
            try:
                toks = json.loads(tokens) if tokens else []
            except ValueError:
                continue
            for tok in toks:
                found = matches(tok)
                if skip:
                    ft = ei.fold(tok)
                    if ft in skipped_docs and ft not in doc_skipped:
                        doc_skipped.add(ft)
                        skipped_docs[ft] += 1
                for eid, kind, adj in found:
                    pr = PRIORITY[kind]
                    old = cur.get(eid)
                    if old is None or pr < old[0]:
                        cur[eid] = (pr, ei.fold(tok), kind, adj)
        if cur_doc is not None:
            flush(cur_doc, cur, rows)
        db.executemany('insert into document_mentions values (?,?,?,?,?,?)', rows)
        db.commit()
        src.close()
        counts[f'excluded_forms_{lang}'] = dict(sorted(skipped_docs.items(), key=lambda kv: -kv[1]))
        log(f'  {lang}: {n_docs} documents scanned')
        counts[f'documents_scanned_{lang}'] = n_docs
    dropped = 0
    if max_form_documents:
        cur = db.execute(
            'delete from document_mentions where (language, form) in (select language, form from '
            'document_mentions group by language, form having count(distinct doc_id) > ?)', (max_form_documents,))
        dropped = cur.rowcount
        counts['rows_dropped_for_stock_forms'] = dropped
        counts['max_form_documents'] = max_form_documents
    db.execute(DOC_INDEX)
    by = {}
    for lang, kind, adj, n in db.execute('select language, kind, adjective, count(*) from document_mentions '
                                         'group by language, kind, adjective'):
        by[f'{lang}/{kind}/{"adjective" if adj else "plain"}'] = n
    counts['rows_by_language_kind'] = by
    counts['rows'] = db.execute('select count(*) from document_mentions').fetchone()[0]
    counts['entities_with_documents'] = db.execute('select count(distinct eid) from document_mentions').fetchone()[0]
    counts['attached_corpus_names'] = n_attached
    db.execute("delete from meta where key in ('document_mentions', 'document_mentions_seconds', "
               "'documents_fingerprint')")
    db.execute("insert into meta values ('document_mentions', ?)", (json.dumps(counts),))
    db.execute("insert into meta values ('documents_fingerprint', ?)", (documents_fingerprint(documents_dir),))
    db.execute("insert into meta values ('document_mentions_seconds', ?)", (str(round(time.time() - t0)),))
    db.commit()
    db.close()
    return counts
