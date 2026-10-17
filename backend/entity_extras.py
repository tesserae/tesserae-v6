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
PREFIX_FORM_MIN = 5


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

    def exact(self, s):
        lo = bisect.bisect_left(self.keys, s)
        hi = bisect.bisect_right(self.keys, s)
        return set(self.eids[lo:hi])


def attach_keys(label_key, forms):
    """(stems, prefix forms, exact forms) a list entity uses to claim corpus names. A stem is a
    label word with its last two letters removed, at least four letters kept. A form of five
    letters or more claims every name that starts with it, a shorter form only an equal name."""
    stems = set()
    for part in (label_key or '').split():
        if len(part) >= STEM_MIN:
            stems.add(part[:max(STEM_MIN, len(part) - 2)])
    prefixes, exact = set(), set()
    for f in forms:
        ff = ei.fold(f)
        if len(ff) >= PREFIX_FORM_MIN:
            prefixes.add(ff)
        elif len(ff) >= 3:
            exact.add(ff)
    return stems, prefixes, exact


def attached_names(index, label_key, forms, excluded=frozenset()):
    """Corpus-name entity ids claimed by a list entity, minus `excluded` (names that are the
    list entity's own forms, which the search already shows as the entity)."""
    stems, prefixes, exact = attach_keys(label_key, forms)
    out = set()
    for s in stems | prefixes:
        out |= index.prefix(s)
    for s in exact:
        out |= index.exact(s)
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

        def tokens_of(pos):
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


# ---------------------------------------------------------------- documents

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
    return attached_names(index, ei.label_key(e['label']), forms, duplicate_names)


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
                    for v in ei.variants(ff, ends)[0]:
                        add(target, v, e['eid'], 'form', False)
            att = attached_for(e, index, name_strings, duplicate_names)
            n_attached += len(att)
            for nid in att:
                for s in name_strings[nid]:
                    add(token_language(s), s, e['eid'], 'corpus_name', e['type'] == 'place' and adjective_form(s))
            if e['type'] == 'place':
                for lg, ends, target in (('la', ei.LA_END, 'la'), ('en', ei.LA_END, 'la'), ('grc', ei.GR_END, 'grc')):
                    sts = set()
                    for f in e['forms'][lg]:
                        ff = ei.fold(f)
                        st = ei.strip_end(ff, ends, STEM_MIN)
                        if len(st) >= STEM_MIN:
                            sts.add(st)
                    if lg == 'la':
                        for part in ei.label_key(e['label']).split():
                            if len(part) >= STEM_MIN:
                                sts.add(part[:max(STEM_MIN, len(part) - 2)])
                    for st in sts:
                        stems[target].setdefault(st[:STEM_MIN], []).append((st, e['eid']))
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
    if 'document_mentions' not in meta:
        problems.append('document_mentions not built: run scripts/build_entity_index.py --documents')
    elif documents_dir and meta.get('documents_fingerprint') != documents_fingerprint(documents_dir):
        problems.append('document_mentions was built against a different documents index: '
                        f'{meta.get("documents_fingerprint")} then, {documents_fingerprint(documents_dir)} now')
    return problems


def build_document_mentions(store_path, documents_dir, log=print, max_form_documents=0):
    """Fill document_mentions in the store: for every list entity and every corpus name, the
    documents whose text holds one of its forms as a whole token, case and accent folded.
    Forms are the entity's name forms with the case endings, the forms of the corpus names
    attached to it, and (places only) any token that starts with one of the place's stems and
    reads as a demonym or an adjective by the suffix rule. One row per entity and document, the
    best kind winning (form, then corpus name, then adjective). Nothing of the document text is
    stored. max_form_documents, when above zero, drops every row of a form that appears in more
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

        def matches(tok):
            hit = cache.get(tok)
            if hit is not None:
                return hit
            f = ei.fold(tok)
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

        def flush():
            for eid, (pr, form, kind, adj) in cur.items():
                rows.append((eid, cur_doc, lang, form, kind, 1 if adj else 0))

        for ref, tokens in src.execute('select ref, tokens from lines order by text_id, rowid'):
            doc = ref.split(' ', 1)[0]
            if doc != cur_doc:
                if cur_doc is not None:
                    flush()
                    if len(rows) >= 50000:
                        db.executemany('insert into document_mentions values (?,?,?,?,?,?)', rows)
                        rows = []
                cur_doc, cur = doc, {}
                n_docs += 1
            try:
                toks = json.loads(tokens) if tokens else []
            except ValueError:
                continue
            for tok in toks:
                for eid, kind, adj in matches(tok):
                    pr = PRIORITY[kind]
                    old = cur.get(eid)
                    if old is None or pr < old[0]:
                        cur[eid] = (pr, ei.fold(tok), kind, adj)
        if cur_doc is not None:
            flush()
        db.executemany('insert into document_mentions values (?,?,?,?,?,?)', rows)
        db.commit()
        src.close()
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
