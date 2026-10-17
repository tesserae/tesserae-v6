"""Entity mentions, stage 3a (2026-10-17): a proper heading for every corpus name, and the frequent
corpus names promoted to full entities after a language-model judgment.

Corpus names (store source 'names', keyed by the first five transliterated letters) used to be
labeled by their most frequent raw form, in whatever script and case. This module

    * chooses a display label from a name's forms and their counts (display_labels),
    * builds the question for the campus gateway and reads the answer (question, parse_judgment),
    * promotes a judged name to an entity of source 'promoted' with id 'pn:<key>' (promote_store).
      A name whose Latin label is a list entity's label or name form merges into that entity: the
      promoted id becomes an alias of the list entity, the list entity's own mentions are left
      exactly as the model pass of stage 1d made them, and the corpus name stays beside it as a
      hidden name listed under it (table entity_merges). A key that holds more than one name (the
      model's "distinct names" answer) promotes only the main name's spellings, and the rest stays
      a plain corpus name.

Nothing here reads the gateway address or the key. The gateway client is backend/entity_gateway.py.
The stored result lives in the table entity_labels (eid, display_label, display_label_la,
display_label_grc, description), so the entities table keeps the layout older code and tests expect.
"""
import json
import re
import unicodedata

from backend import entity_extras as extras
from backend import entity_index as ei
from backend import entity_model_pass as mp

TYPES = ('person', 'place', 'deity', 'people', 'other')
PROMOTED_TYPES = ('person', 'place', 'deity', 'people')
PROVENANCE = 'Named in the corpus, identified by a language model'
MIN_LINES = 10
MIN_WORKS = 3
SNIPPET_LINES = 3
MAX_FORMS = 12
LABEL_SCHEMA = '''
CREATE TABLE IF NOT EXISTS entity_labels (eid INTEGER PRIMARY KEY, display_label TEXT, display_label_la TEXT,
  display_label_grc TEXT, description TEXT);
CREATE TABLE IF NOT EXISTS entity_merges (eid INTEGER PRIMARY KEY, list_eid INTEGER);
'''

# ---------------------------------------------------------------- display labels

# Endings that read as a nominative (checked on the accent-stripped lower-case form). The strong
# ones are nominatives that are rarely another case. The weak ones are nominatives too (Roma,
# Helene) but are also the accusative, ablative or genitive of other names (Sarpedona, Sarpedonis),
# so a count is weighted by its ending (TIER_WEIGHT) and the form with the largest weighted count wins.
LA_STRONG = ('us', 'um', 'on', 'es', 'or')
LA_WEAK = ('a', 'is', 'o', 'as', 'e')
GR_STRONG = ('ων', 'ος', 'ης', 'ευς')
GR_WEAK = ('η', 'α', 'ις', 'ω')


def script_of(s):
    for ch in s:
        if ch.isalpha():
            n = unicodedata.name(ch, '')
            if n.startswith('LATIN'):
                return 'latin'
            if n.startswith('GREEK'):
                return 'greek'
            return 'other'
    return 'other'


def _plain(form):
    return ei.COMB.sub('', unicodedata.normalize('NFD', form)).lower().replace('ς', 'σ').replace('ϲ', 'σ')


def nominative_tier(form, script):
    """0 for a strong nominative ending, 1 for a weak one, 2 for neither."""
    f = _plain(form)
    if script == 'latin':
        strong, weak = LA_STRONG, LA_WEAK
    elif script == 'greek':
        strong, weak = tuple(_plain(x) for x in GR_STRONG), tuple(_plain(x) for x in GR_WEAK)
    else:
        return 2
    if f.endswith(strong):
        return 0
    return 1 if f.endswith(weak) else 2


def _capitalized(form, mixed_exists):
    if len(form) > 1 and form.isupper() and not mixed_exists:
        return form[0] + form[1:].lower()
    return form[0].upper() + form[1:]


def _acute(form):
    """A grave accent in running Greek stands for a final acute (Σαρπηδὼν for Σαρπηδών)."""
    return unicodedata.normalize('NFC', unicodedata.normalize('NFD', form).replace('̀', '́'))


# How much an ending is worth against frequency: a count is multiplied by the weight of the form's
# ending, so a strong nominative beats an oblique form unless the oblique form is several times
# more frequent (Iolen 21 against Iolenses 1).
TIER_WEIGHT = (1.0, 0.25, 0.1)


def best_form(forms, script):
    """The best display form of the given script from {form: count}, or None."""
    cand = {}
    for f, n in forms.items():
        if f and script_of(f) == script:
            f = _acute(f) if script == 'greek' else f
            cand[f] = cand.get(f, 0) + n
    if not cand:
        return None
    mixed = any(not (len(f) > 1 and f.isupper()) for f in cand)
    pool = {f: n for f, n in cand.items() if not (mixed and len(f) > 1 and f.isupper())}
    top = min(pool, key=lambda f: (-pool[f] * TIER_WEIGHT[nominative_tier(f, script)], nominative_tier(f, script), f))
    return _capitalized(top, mixed)


def display_labels(forms):
    """(display_label, display_label_la, display_label_grc) from {raw form: count}. A Latin-script
    form is the heading when one exists, else the best Greek form, else the most frequent form."""
    la = best_form(forms, 'latin')
    grc = best_form(forms, 'greek')
    if la or grc:
        return la or grc, la, grc
    other = max(forms, key=lambda f: (forms[f], f)) if forms else None
    return other, None, None


# ---------------------------------------------------------------- the gateway question

SYSTEM = (
    'You help catalog the proper names found in a corpus of ancient Latin, Greek and English texts. You are '
    'given a name key (the first letters of a name, so a key can hold more than one name), the spellings found '
    'under it with their counts, and three lines from different works. Answer with one JSON object and nothing '
    'else, with these fields.\n'
    '"type": person (a named individual, human or mythical), place (a city, region, river, mountain, island, '
    'building), deity (a god or goddess), people (an ethnic or tribal name or a named group, for example the '
    'Sabines), or other (a common word, a title, an adjective, a month, a non-name).\n'
    '"latin": the standard English or Latin nominative name, for example Sarpedon, Aeneas, Mount Olympus. '
    'Empty for type other.\n'
    '"greek": the Greek nominative, accented, if the name is Greek or has Greek spellings among those listed, '
    'else an empty string.\n'
    '"description": at most twelve words saying who or what it is and when. Empty for type other.\n'
    '"distinct_names": true when the spellings listed belong to more than one distinct name (a key such as '
    'sarpe holds both Sarpedon and Sarpedonius), else false.\n'
    '"main_forms": when distinct_names is true, the spellings listed, copied exactly, that belong to the '
    'name with the most spellings, else an empty list.\n'
    'Judge the name from the spellings and the lines together. A name that appears only as an adjective or as a '
    'common word is type other.')


def question(key, forms, snippets):
    """forms: [(spelling, count)], snippets: [(author, language, line)]."""
    lines = [f'Key: {key}', 'Spellings found: ' + ', '.join(f'{f} ({n})' for f, n in forms), 'Lines:']
    for i, (author, lang, text) in enumerate(snippets, 1):
        lines.append(f'{i}. [{author}, {lang}] {text}')
    return '\n'.join(lines)


def _json_object(text):
    if not text:
        return None
    t = text.strip()
    t = re.sub(r'^```(?:json)?|```$', '', t, flags=re.M).strip()
    a, b = t.find('{'), t.rfind('}')
    if a < 0 or b <= a:
        return None
    try:
        obj = json.loads(t[a:b + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def parse_judgment(text, spellings):
    """The judgment as a dict (type, latin, greek, description, distinct_names, main_forms) or None
    for an unusable reply. main_forms keeps only spellings that were listed. A split with no
    usable main form is read as no split."""
    obj = _json_object(text)
    if obj is None:
        return None
    typ = str(obj.get('type') or '').strip().lower()
    if typ not in TYPES:
        return None
    clean = lambda v: re.sub(r'\s+', ' ', str(v or '')).strip()  # noqa: E731
    latin, greek = clean(obj.get('latin')), clean(obj.get('greek'))
    desc = ' '.join(clean(obj.get('description')).split()[:14])
    if typ in PROMOTED_TYPES and not latin:
        return None
    listed = {ei.fold(s): s for s in spellings}
    main = []
    if obj.get('distinct_names') is True and isinstance(obj.get('main_forms'), list):
        for m in obj['main_forms']:
            s = listed.get(ei.fold(str(m)))
            if s and s not in main:
                main.append(s)
    split = bool(main) and len(main) < len(spellings)
    return {'type': typ, 'latin': latin, 'greek': greek, 'description': desc,
            'distinct_names': split, 'main_forms': main if split else []}


# ---------------------------------------------------------------- store work

def store_forms(db):
    """{eid: {raw form: mention rows}} for every entity with mention rows."""
    out = {}
    for eid, form, n in db.execute('select eid, form, count(*) from mention_rows group by eid, form'):
        out.setdefault(eid, {})[form] = n
    return out


def write_display_labels(db, log=print):
    """Step 1. A display label for every corpus name, and the Greek form beside the label of every
    list entity that has one among its mentions. entities.label of a corpus name becomes its
    display label. Returns the (eid, old label, new label) of the names that changed."""
    db.executescript(LABEL_SCHEMA)
    forms = store_forms(db)
    changed = []
    rows = []
    for eid, typ, label, source in db.execute('select eid, type, label, source from entities').fetchall():
        f = forms.get(eid, {})
        if source == 'names':
            disp, la, grc = display_labels(f)
            disp = disp or label
            if disp != label:
                changed.append((eid, label, disp))
            rows.append((eid, disp, la, grc, None))
        elif source == 'list':
            rows.append((eid, label, label, best_form(f, 'greek'), None))
    db.executemany('insert or replace into entity_labels(eid, display_label, display_label_la, display_label_grc, '
                   'description) values (?,?,?,?,?)', rows)
    db.executemany('update entities set label = ? where eid = ?', [(new, eid) for eid, _o, new in changed])
    log(f'display labels: {len(rows)} rows, {len(changed)} corpus-name labels changed')
    return changed


def frequent_names(db, min_lines=MIN_LINES, min_works=MIN_WORKS):
    """{eid: (lines, works)} for the corpus names with at least min_lines lines in min_works works."""
    key = extras.LINE_GROUP_SQL
    out = {}
    q = (f"select m.eid, count(distinct w.work || '|' || {key}), count(distinct w.work) "  # nosec B608
         "from mention_rows m join windows w on w.wid = m.wid join entities e on e.eid = m.eid "
         "where e.source = 'names' group by m.eid")
    for eid, lines, works in db.execute(q):
        if lines >= min_lines and works >= min_works:
            out[eid] = (lines, works)
    return out


# ---------------------------------------------------------------- promotion

COMPATIBLE = {'person': ('person', 'patronymic', 'epithet', 'deity'), 'deity': ('deity', 'person'),
              'place': ('place',), 'people': ()}


def list_lookup(db):
    """{folded string: [list eids]}: each list entity's folded label, label key and name forms with
    the case endings the matcher allows (extras.case_variants)."""
    ents = {}
    for eid, typ, label in db.execute("select eid, type, label from entities where source = 'list'"):
        ents[eid] = (typ, label)
    forms = {}
    for eid, form, lang in db.execute("select eid, form, language from variants where source = 'list'"):
        forms.setdefault(eid, []).append((form, lang))
    look = {}

    def add(s, eid):
        if s and eid not in look.setdefault(s, []):
            look[s].append(eid)

    for eid, (typ, label) in ents.items():
        add(ei.fold(label), eid)
        add(ei.label_key(label), eid)
        for form, lang in forms.get(eid, ()):
            f = ei.fold(form)
            if len(f) >= 3:
                for v in extras.case_variants(f, ei.GR_END if lang == 'grc' else ei.LA_END):
                    add(v, eid)
    return ents, look


def merge_target(latin, typ, ents, look):
    """The list eid a promoted name merges into, 'ambiguous' when several list entities of a
    compatible type carry the label, or None."""
    if not latin or typ not in COMPATIBLE:
        return None
    cands = []
    for s in {ei.fold(latin), ei.label_key(latin)}:
        for eid in look.get(s, ()):
            if ents[eid][0] in COMPATIBLE[typ] and eid not in cands:
                cands.append(eid)
    if len(cands) > 1:
        exact = [e for e in cands if ents[e][0] == typ]
        cands = exact if len(exact) == 1 else cands
    if not cands:
        return None
    return cands[0] if len(cands) == 1 else 'ambiguous'


def _move_rows(db, src, dst, main_folds):
    """Move mention rows and document rows of the forms in main_folds (None: all) from src to dst,
    leaving out the rows dst already has for the same window and token. Returns (moved, dropped)."""
    have = {(wid, fk) for wid, fk in db.execute('select wid, coalesce(form_key, lower(form)) from mention_rows '
                                                'where eid = ?', (dst,))}
    moved = dropped = 0
    mv, rm = [], []
    for rowid, wid, form, fk in db.execute('select rowid, wid, form, coalesce(form_key, lower(form)) '
                                           'from mention_rows where eid = ?', (src,)).fetchall():
        if main_folds is not None and ei.fold(form) not in main_folds:
            continue
        if (wid, fk) in have:
            rm.append((rowid,))
            dropped += 1
        else:
            mv.append((dst, rowid))
            have.add((wid, fk))
            moved += 1
    db.executemany('update mention_rows set eid = ? where rowid = ?', mv)
    db.executemany('delete from mention_rows where rowid = ?', rm)
    if db.execute("select 1 from sqlite_master where name = 'document_mentions'").fetchone():
        seen = {(d, f) for d, f in db.execute('select doc_id, form from document_mentions where eid = ?', (dst,))}
        mv, rm = [], []
        for rowid, doc, form in db.execute('select rowid, doc_id, form from document_mentions where eid = ?',
                                           (src,)).fetchall():
            if main_folds is not None and ei.fold(form) not in main_folds:
                continue
            if (doc, form) in seen:
                rm.append((rowid,))
            else:
                mv.append((dst, rowid))
                seen.add((doc, form))
        db.executemany('update document_mentions set eid = ? where rowid = ?', mv)
        db.executemany('delete from document_mentions where rowid = ?', rm)
    return moved, dropped


def _refresh_windows(db, eids):
    for eid in eids:
        n = db.execute('select count(distinct wid) from mention_rows where eid = ?', (eid,)).fetchone()[0]
        db.execute('update entities set n_windows = ? where eid = ?', (n, eid))


def promote_store(db, judgments, log=print):
    """Step 3. `judgments`: {name key: judgment dict from parse_judgment}. Every key judged person,
    place, deity or people becomes an entity of source 'promoted' (id pn:<key>) or merges into a
    list entity. A key whose spellings hold more than one name promotes only the main name's
    spellings, the rest stays a plain corpus name. Returns a report dict with the examples."""
    db.executescript(LABEL_SCHEMA)
    ents, look = list_lookup(db)
    by_key = {k: eid for eid, k in db.execute("select eid, name_key from entities where source = 'names'")}
    next_eid = db.execute('select max(eid) from entities').fetchone()[0] + 1
    rep = {'promoted': 0, 'merged': 0, 'ambiguous': 0, 'split_promoted': 0, 'by_type': {}, 'missing_key': 0,
           'promoted_examples': [], 'merged_examples': [], 'ambiguous_examples': [],
           'split_examples': []}
    touched = set()
    for key in sorted(judgments):
        j = judgments[key]
        if j['type'] not in PROMOTED_TYPES:
            continue
        eid = by_key.get(key)
        if eid is None:
            rep['missing_key'] += 1
            continue
        old_label = db.execute('select label from entities where eid = ?', (eid,)).fetchone()[0]
        main = {ei.fold(f) for f in j['main_forms']} if j['distinct_names'] else None
        target = merge_target(j['latin'], j['type'], ents, look)
        variants = [v for v in db.execute('select form, language, role, source from variants where eid = ?', (eid,))]
        main_variants = [v for v in variants if main is None or v[0] in main or ei.fold(v[0]) in main]
        label_fold = ei.fold(j['latin'])
        if main is not None:
            rep['split_promoted'] += 1
            if len(rep['split_examples']) < 20:
                rep['split_examples'].append({'key': key, 'latin': j['latin'], 'main_forms': j['main_forms'][:6]})
        if isinstance(target, int):
            # The list entity keeps its own mentions exactly as the model pass left them. The
            # corpus name (only the main name's spellings of a split key) stays a hidden name
            # attached to it, and the promoted id is an alias of the list entity.
            src = eid
            if main is not None:
                src = next_eid
                next_eid += 1
                db.execute('insert into entities(eid, entity_id, type, label, source, name_key, distinctive, n_windows) '
                           "values (?, ?, 'name', ?, 'names', ?, 0, 0)", (src, f'nm:{key}:main', old_label, key))
                _move_rows(db, eid, src, main)
                for f, lang, role, srcname in main_variants:
                    db.execute('update variants set eid = ? where eid = ? and form = ?', (src, eid, f))
                touched.update((src, eid))
            db.execute('insert or replace into entity_merges values (?, ?)', (src, target))
            db.execute('insert into entity_aliases values (?,?,?,?,?)', (target, f'pn:{key}', j['latin'], j['type'], 'promoted_merge'))
            touched.add(src)
            rep['merged'] += 1
            if len(rep['merged_examples']) < 20:
                rep['merged_examples'].append({'key': key, 'latin': j['latin'], 'type': j['type'], 'into': ents[target][1]})
            continue
        if target == 'ambiguous':
            rep['ambiguous'] += 1
            if len(rep['ambiguous_examples']) < 20:
                rep['ambiguous_examples'].append({'key': key, 'latin': j['latin'], 'type': j['type']})
        if main is None:
            new = eid
        else:
            new = next_eid
            next_eid += 1
            db.execute('insert into entities(eid, entity_id, type, label, source, name_key, distinctive, n_windows) '
                       "values (?, ?, ?, ?, 'names', ?, 0, 0)", (new, f'pn:{key}', j['type'], j['latin'], key))
            _move_rows(db, eid, new, main)
            for f, lang, role, src in main_variants:
                db.execute('update variants set eid = ? where eid = ? and form = ?', (new, eid, f))
            touched.update((new, eid))
        db.execute("update entities set entity_id = ?, type = ?, label = ?, source = 'promoted' where eid = ?",
                   (f'pn:{key}', j['type'], j['latin'], new))
        if label_fold and not db.execute('select 1 from variants where eid = ? and form = ?', (new, label_fold)).fetchone():
            db.execute('insert into variants values (?,?,?,?,?)', (new, label_fold, '', 'form', 'promoted'))
        db.execute('insert or replace into entity_labels values (?,?,?,?,?)',
                   (new, j['latin'], j['latin'], j['greek'] or None, j['description'] or None))
        if main is None:
            db.execute('insert into entity_aliases values (?,?,?,?,?)', (new, f'nm:{key}', old_label, 'name', 'corpus_name'))
        touched.add(new)
        rep['promoted'] += 1
        rep['by_type'][j['type']] = rep['by_type'].get(j['type'], 0) + 1
        if len(rep['promoted_examples']) < 20 and target is None:
            rep['promoted_examples'].append({'key': key, 'latin': j['latin'], 'greek': j['greek'], 'type': j['type'],
                                             'description': j['description'], 'was': old_label})
    # a split leaves a plain corpus name whose heading is recomputed from the forms it kept
    forms = store_forms(db)
    for eid in sorted(touched):
        row = db.execute('select source from entities where eid = ?', (eid,)).fetchone()
        if row and row[0] == 'names':
            disp, la, grc = display_labels(forms.get(eid, {}))
            if disp:
                db.execute('update entities set label = ? where eid = ?', (disp, eid))
                db.execute('insert or replace into entity_labels values (?,?,?,?,NULL)', (eid, disp, la, grc))
    _refresh_windows(db, touched)
    log(f"promoted {rep['promoted']}, merged {rep['merged']}, ambiguous {rep['ambiguous']}, split {rep['split_promoted']}")
    return rep


# ---------------------------------------------------------------- context lines

def context_lines(db, tx, eid, n=5, tag=''):
    """Up to n lines of a name's mentions from n different works: [author, language, line]. The
    choice is seeded by the entity's name key and `tag`, so a rerun gives the same lines."""
    import random
    lang_name = {'la': 'Latin', 'grc': 'Greek', 'en': 'English'}
    key = db.execute('select name_key, entity_id from entities where eid = ?', (eid,)).fetchone()
    rnd = random.Random(f'{tag}:{key[0] or key[1]}')
    by_work = {}
    for work, lang, form, ref in db.execute(
            'select w.work, w.language, m.form, m.line_ref from mention_rows m join windows w on w.wid = m.wid '
            'where m.eid = ? and m.line_ref is not null order by m.wid', (eid,)):
        by_work.setdefault(work, []).append((lang, form, ref))
    works = sorted(by_work)
    rnd.shuffle(works)
    out = []
    for work in works:
        lang, form, ref = rnd.choice(by_work[work])
        r = tx.execute('select text from lines where work = ? and ref = ? limit 1', (work, ref)).fetchone()
        if not r or form not in r[0]:
            continue
        out.append([mp.author_of(work), lang_name.get(lang, lang), mp.line_snippet(r[0], form, 160)])
        if len(out) == n:
            break
    return out


# ---------------------------------------------------------------- a split that contradicts its label

def _common_prefix(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def contradicts_label(j):
    """True when a split answer (distinct names) lists main spellings that share no five-letter
    start (three for a short label) with the transliterated Latin or Greek label: the key rhodo
    answered Rhodes and listed the spellings of Rhodope."""
    if not j.get('distinct_names') or j['type'] not in PROMOTED_TYPES:
        return False
    labels = [ei.translit(x) for x in (j['latin'], j['greek']) if x]
    mains = [ei.translit(f) for f in j['main_forms']]
    for lab in labels:
        for m in mains:
            if lab and m and _common_prefix(lab, m) >= min(5, len(lab), len(m)):
                return False
    return True


SPLIT_SYSTEM = (
    'You help catalog the proper names found in a corpus of ancient Latin, Greek and English texts. You are given '
    'a name, its type, the spellings found under one key with their counts, and five lines from different works. '
    'The key can hold more than one name. Say which of the listed spellings belong to the given name as these lines '
    'use it. Answer with one JSON object and nothing else, {"belong": [the spellings, copied exactly]}.')


def split_question(label, typ, forms, snippets):
    lines = [f'Name: {label} ({typ})', 'Spellings found: ' + ', '.join(f'{f} ({n})' for f, n in forms), 'Lines:']
    for i, (author, lang, text) in enumerate(snippets, 1):
        lines.append(f'{i}. [{author}, {lang}] {text}')
    return '\n'.join(lines)


def parse_split(text, spellings):
    """The listed spellings the model says belong to the name, or None for an unusable reply."""
    obj = _json_object(text)
    if obj is None or not isinstance(obj.get('belong'), list):
        return None
    listed = {ei.fold(s): s for s in spellings}
    out = []
    for m in obj['belong']:
        sp = listed.get(ei.fold(str(m)))
        if sp and sp not in out:
            out.append(sp)
    return out


def apply_split_fix(judgments, fixes):
    """Replace main_forms by the confirmed spellings. fixes: {key: [spellings]}. A key whose fix is
    empty is left as it was. Returns the number of groups changed."""
    n = 0
    for key, belong in fixes.items():
        j = judgments.get(key)
        if not j or not belong:
            continue
        if set(belong) != set(j['main_forms']):
            n += 1
        j['main_forms'] = belong
        j['distinct_names'] = True
    return n


# ---------------------------------------------------------------- duplicates among promoted entities

def dedupe_promoted(db, log=print):
    """Merge promoted entities that share a type and a folded Latin label, or whose Latin label
    equals another's Greek label after the names transliteration. The survivor is the one with
    the most lines. Every key stays in entity_aliases, forms, mentions and documents are united."""
    lines = {}
    for (eid, _lang), n in extras.line_counts(db).items():
        lines[eid] = lines.get(eid, 0) + n
    ents = {}
    for eid, entity_id, typ, label in db.execute("select eid, entity_id, type, label from entities where source = 'promoted'"):
        ents[eid] = {'id': entity_id, 'type': typ, 'label': label, 'greek': None}
    for eid, grc in db.execute('select eid, display_label_grc from entity_labels'):
        if eid in ents:
            ents[eid]['greek'] = grc
    parent = {e: e for e in ents}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    first, by_trans = {}, {}
    for eid, e in ents.items():
        first.setdefault((e['type'], ei.fold(e['label'])), []).append(eid)
        by_trans.setdefault((e['type'], ei.translit(e['label'])), []).append(eid)
    for grp in first.values():
        for x in grp[1:]:
            union(grp[0], x)
    for eid, e in ents.items():
        if e['greek']:
            for other in by_trans.get((e['type'], ei.translit(e['greek'])), ()):
                union(eid, other)
    groups = {}
    for eid in ents:
        groups.setdefault(find(eid), []).append(eid)
    rep = {'before': len(ents), 'groups': 0, 'merged_away': 0, 'examples': []}
    touched = []
    for members in groups.values():
        if len(members) < 2:
            continue
        surv = max(members, key=lambda e: (lines.get(e, 0), -e))
        rep['groups'] += 1
        for other in members:
            if other == surv:
                continue
            _move_rows(db, other, surv, None)
            have = {v[0] for v in db.execute('select form from variants where eid = ?', (surv,))}
            db.executemany('insert into variants values (?,?,?,?,?)',
                           [(surv, f, lang, role, src) for f, lang, role, src in
                            db.execute('select form, language, role, source from variants where eid = ?', (other,)).fetchall()
                            if f not in have])
            db.execute('delete from variants where eid = ?', (other,))
            db.execute('update entity_aliases set eid = ? where eid = ?', (surv, other))
            db.execute('insert into entity_aliases values (?,?,?,?,?)',
                       (surv, ents[other]['id'], ents[other]['label'], ents[other]['type'], 'promoted_duplicate'))
            if not ents[surv]['greek'] and ents[other]['greek']:
                db.execute('update entity_labels set display_label_grc = ? where eid = ?', (ents[other]['greek'], surv))
                ents[surv]['greek'] = ents[other]['greek']
            db.execute('delete from entity_labels where eid = ?', (other,))
            db.execute('delete from entities where eid = ?', (other,))
            rep['merged_away'] += 1
        touched.append(surv)
        if len(rep['examples']) < 20:
            rep['examples'].append({'label': ents[surv]['label'], 'type': ents[surv]['type'], 'kept': ents[surv]['id'],
                                    'also': sorted(ents[m]['id'] for m in members if m != surv),
                                    'lines': sum(lines.get(m, 0) for m in members)})
    _refresh_windows(db, touched)
    rep['after'] = rep['before'] - rep['merged_away']
    log(f"promoted entities {rep['before']} -> {rep['after']} in {rep['groups']} groups")
    return rep


# ---------------------------------------------------------------- the description confirmation

CONFIRM_SYSTEM = (
    'You help catalog the proper names found in a corpus of ancient Latin, Greek and English texts. You are given a '
    'name with its Latin and Greek labels, its type, a one-line description, and five lines from different works. '
    'Is this description right for the name as these lines use it? Answer with one JSON object and nothing else, '
    '{"answer": "yes" or "no", "description": a corrected description of at most twelve words, empty when the '
    'answer is yes}.')


def confirm_question(latin, greek, typ, description, snippets):
    lines = [f'Name: {latin}' + (f' · {greek}' if greek else ''), f'Type: {typ}', f'Description: {description}', 'Lines:']
    for i, (author, lang, text) in enumerate(snippets, 1):
        lines.append(f'{i}. [{author}, {lang}] {text}')
    return '\n'.join(lines)


def parse_confirm(text):
    """(True, '') for yes, (False, corrected description) for no, None for an unusable reply."""
    obj = _json_object(text)
    if obj is None:
        return None
    a = str(obj.get('answer') or '').strip().lower()
    if a.startswith('y'):
        return True, ''
    if a.startswith('n'):
        return False, ' '.join(re.sub(r'\s+', ' ', str(obj.get('description') or '')).strip().split()[:14])
    return None


def final_description(original, first, second):
    """The description to store. first: the parse_confirm result for the original, second: the one
    for the correction (or None when none was asked). Kept when the model confirms the original,
    or corrects it and then confirms the correction, else empty."""
    if first is None:
        return ''
    if first[0]:
        return original or ''
    if first[1] and second is not None and second[0]:
        return first[1]
    return ''


def apply_descriptions(db, final):
    """final: {eid: description}. Stores them in entity_labels (empty as NULL)."""
    db.executemany('update entity_labels set description = ? where eid = ?', [(d or None, eid) for eid, d in final.items()])
