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
import os
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


# Stage 4. Types whose heading must be a place name and not a demonym or adjective made from it. A person is
# left out (Latin -anus and -inus are ordinary endings of personal names) and so are people (fix pass 4b), whose
# own name is a demonym.
PLACE_TYPES = ('place', 'region')
DEMONYM_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'entity_demonym_suffixes.json')
_demonyms = {}


def demonym_suffixes():
    """{'latin': (endings), 'greek': (accent-stripped endings)} from entity_demonym_suffixes.json."""
    if not _demonyms:
        d = json.load(open(DEMONYM_PATH, encoding='utf-8'))
        _demonyms['latin'] = tuple(x.lower() for x in d['la'])
        _demonyms['greek'] = tuple(_plain(x) for x in d['grc'])
    return _demonyms


def is_demonym(form, script):
    """True when the form ends in a demonym or adjective ending of the suffix file."""
    ends = demonym_suffixes().get(script)
    return bool(ends) and _plain(form).endswith(ends)


def first_declension_heading(pool):
    """Stage 4. The nominative in -a built from the stem when every Latin place-name form is an oblique
    first-declension form (-am or -ae), with the nominative in -a of the same stem allowed among them:
    massiliam and massiliae give Massilia, and so do massiliam and Massilia. At least one form in -am is
    required, because -ae alone can be a plural nominative (Athenae, Baiae) and then the attested form is the
    heading. A form of another shape (Massilias, Massinissa) means the rule does not apply and the weighted
    count decides. Returns the heading in lower case or None."""
    plain = {f: _plain(f) for f in pool}
    oblique = [f for f in pool if plain[f].endswith(('am', 'ae'))]
    if not any(plain[f].endswith('am') for f in oblique):
        return None
    stems = {plain[f][:-2] for f in oblique}
    if any(plain[f] not in {st + 'a' for st in stems} for f in pool if f not in oblique):
        return None
    top = max(oblique, key=lambda f: (pool[f], f))
    return plain[top][:-2] + 'a'


def best_form(forms, script, place=False):
    """The best display form of the given script from {form: count}, or None. With place=True (an entity
    of a place type, stage 4) a demonym or adjective form ranks below every place-name form, and when every
    Latin place-name form is an oblique first-declension form the heading is the nominative built from the
    stem (first_declension_heading)."""
    cand = {}
    for f, n in forms.items():
        if f and script_of(f) == script:
            f = _acute(f) if script == 'greek' else f
            cand[f] = cand.get(f, 0) + n
    if not cand:
        return None
    mixed = any(not (len(f) > 1 and f.isupper()) for f in cand)
    pool = {f: n for f, n in cand.items() if not (mixed and len(f) > 1 and f.isupper())}
    if place:
        names = {f: n for f, n in pool.items() if not is_demonym(f, script)}
        pool = names or pool
        if script == 'latin' and names:
            built = first_declension_heading(names)
            if built:
                return _capitalized(built, mixed)
    top = min(pool, key=lambda f: (-pool[f] * TIER_WEIGHT[nominative_tier(f, script)], nominative_tier(f, script), f))
    return _capitalized(top, mixed)


def display_labels(forms, place=False):
    """(display_label, display_label_la, display_label_grc) from {raw form: count}. A Latin-script
    form is the heading when one exists, else the best Greek form, else the most frequent form."""
    la = best_form(forms, 'latin', place)
    grc = best_form(forms, 'greek', place)
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


def write_display_labels(db, log=print, people_pleiades=None):
    """Step 1. A display label for every corpus name, and the Greek form beside the label of every
    list entity that has one among its mentions. entities.label of a corpus name becomes its
    display label. Returns the (eid, old label, new label) of the names that changed."""
    db.executescript(LABEL_SCHEMA)
    forms = store_forms(db)
    changed = []
    rows = []
    people_pleiades = people_pleiades or set()
    for eid, typ, label, source, pid, cands in db.execute(
            'select eid, type, label, source, pleiades_id, pleiades_candidates from entities').fetchall():
        if people_pleiades and source == 'list' and typ in PLACE_TYPES:
            ids = {str(pid)} if pid else set()
            try:
                ids |= {str(x) for x in json.loads(cands)} if cands else set()
            except ValueError:
                pass
            if ids & people_pleiades:
                typ = 'people'          # Pleiades lists the place as a people: its own name is a demonym
        f = forms.get(eid, {})
        if source == 'names':
            disp, la, grc = display_labels(f)
            disp = disp or label
            if disp != label:
                changed.append((eid, label, disp))
            rows.append((eid, disp, la, grc, None))
        elif source == 'list':
            rows.append((eid, label, label, best_form(f, 'greek', typ in PLACE_TYPES), None))
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


def greek_stems_of_store(db):
    """The stems of every Greek-script spelling the store holds (variants and mention forms), for the check
    that a Greek label the model gave a collision group is a name the corpus spells."""
    out = set()
    for (f,) in db.execute('select distinct form from variants union select distinct form from mention_rows'):
        if f and script_of(f) == 'greek':
            out.add(_greek_stem(f))
    return out


def promote_store(db, judgments, log=print, greek_stems=None):
    """Step 3. `judgments`: {name key: judgment dict from parse_judgment}. Every key judged person,
    place, deity or people becomes an entity of source 'promoted' (id pn:<key>) or merges into a
    list entity. A key whose spellings hold more than one name promotes only the main name's
    spellings, the rest stays a plain corpus name. Returns a report dict with the examples.

    Stage 4. A judgment of a collision group (collision_judgments) has the field 'base', the five-letter
    key it was carved from, and a key of its own (the first six letters of its spellings). Its entity id is
    pn:<its key>, the rows of its spellings leave the corpus name of the base key, and its Greek label is kept
    only when the corpus spells a Greek name with that stem (greek_stems). The group that keeps the id of the
    key's earlier judgment (field entity_key) is the same entity as before and keeps the earlier label rules."""
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
        eid = by_key.get(j.get('base', key))
        if eid is None:
            rep['missing_key'] += 1
            continue
        ekey = j.get('entity_key', key)        # the id the entity takes is pn:<ekey> (a collision heir keeps the old key)
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
            db.execute('insert into entity_aliases values (?,?,?,?,?)', (target, f'pn:{ekey}', j['latin'], j['type'], 'promoted_merge'))
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
            db.execute('insert into entities(eid, entity_id, type, label, source, name_key, distinctive, n_windows, homonym_group) '
                       "values (?, ?, ?, ?, 'names', ?, 0, 0, ?)",
                       (new, f'pn:{ekey}', j['type'], j['latin'], key, COLLISION_MARK if 'base' in j else None))
            _move_rows(db, eid, new, main)
            for f, lang, role, src in main_variants:
                db.execute('update variants set eid = ? where eid = ? and form = ?', (new, eid, f))
            touched.update((new, eid))
        db.execute("update entities set entity_id = ?, type = ?, label = ?, source = 'promoted' where eid = ?",
                   (f'pn:{ekey}', j['type'], j['latin'], new))
        if label_fold and not db.execute('select 1 from variants where eid = ? and form = ?', (new, label_fold)).fetchone():
            db.execute('insert into variants values (?,?,?,?,?)', (new, label_fold, '', 'form', 'promoted'))
        grc = j['greek'] or None
        ok = False
        label_forms = j['label_forms'] if 'label_forms' in j else [v[0] for v in main_variants]
        for cand in ([grc] if grc else []) + list(j.get('greek_alternatives', ())):
            if 'base' in j and 'entity_key' not in j and greek_stems is not None and _greek_stem(cand) not in greek_stems:
                continue          # a new name carved from a collision: its Greek label must be a spelling the corpus has
            if greek_label_ok(cand, label_forms):
                grc, ok = cand, True
                break
        if grc and not ok:
            rep['greek_label_dropped'] = rep.get('greek_label_dropped', 0) + 1
            if len(rep.setdefault('greek_label_dropped_examples', [])) < 40:
                rep['greek_label_dropped_examples'].append({'key': key, 'latin': j['latin'], 'greek': grc})
            grc = None
        db.execute('insert or replace into entity_labels values (?,?,?,?,?)',
                   (new, j['latin'], j['latin'], grc, j['description'] or None))
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

def context_lines(db, tx, eid, n=5, tag='', only=None):
    """Up to n lines of a name's mentions from n different works: [author, language, line]. The
    choice is seeded by the entity's name key and `tag`, so a rerun gives the same lines. With `only`
    (a set of folded spellings) just the mentions of those spellings are used."""
    import random
    lang_name = {'la': 'Latin', 'grc': 'Greek', 'en': 'English'}
    key = db.execute('select name_key, entity_id from entities where eid = ?', (eid,)).fetchone()
    rnd = random.Random(f'{tag}:{key[0] or key[1]}')
    by_work = {}
    for work, lang, form, ref in db.execute(
            'select w.work, w.language, m.form, m.line_ref from mention_rows m join windows w on w.wid = m.wid '
            'where m.eid = ? and m.line_ref is not null order by m.wid', (eid,)):
        if only is not None and ei.fold(form) not in only:
            continue
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


# ---------------------------------------------------------------- the Greek label and the label of a split (stage 3b)

def _greek_stem(s):
    """The folded form minus a nominative or case ending of the matcher's list, three letters left at least."""
    return ei.strip_end(ei.fold(s), ei.GR_END, 3)


def greek_label_ok(greek, forms=()):
    """Fix pass. A promoted entity keeps its Greek label when it has no Greek-script form (the stage 3a
    behavior) or when at least one Greek-script form's stem starts with the label's stem and the label's
    stem is at least as long as that form's stem minus two letters. Key equality dropped labels that
    are right (Abraham, Baruch, Apulia), because a Greek spelling and a Latin spelling of one name have
    different transliterated keys."""
    if not greek:
        return False
    gf = [f for f in forms if script_of(f) == 'greek']
    if not gf:
        return True
    ls = _greek_stem(greek)
    return any(_greek_stem(f).startswith(ls) and len(ls) >= len(_greek_stem(f)) - 2 for f in gf)


LABEL_SYSTEM = (
    'You help catalog the proper names found in a corpus of ancient Latin, Greek and English texts. You are given '
    'the type of a name, the spellings that belong to it with their counts, and five lines from different works '
    'that use these spellings. Say what the name is. Answer with one JSON object and nothing else, '
    '{"latin": the standard English or Latin nominative name, "greek": the Greek nominative, accented, if the '
    'spellings are Greek or have Greek forms, else an empty string}. The name must be the one these spellings '
    'spell, not a similar name.')


def label_question(typ, forms, snippets):
    lines = [f'Type: {typ}', 'Spellings: ' + ', '.join(f'{f} ({n})' for f, n in forms), 'Lines:']
    for i, (author, lang, text) in enumerate(snippets, 1):
        lines.append(f'{i}. [{author}, {lang}] {text}')
    return '\n'.join(lines)


def parse_label(text):
    """(latin, greek) from the label question's reply, or None for an unusable reply."""
    obj = _json_object(text)
    if obj is None:
        return None
    clean = lambda v: re.sub(r'\s+', ' ', str(v or '')).strip()  # noqa: E731
    latin, greek = clean(obj.get('latin')), clean(obj.get('greek'))
    return (latin, greek) if latin else None


def _one_script(label, script):
    letters = [c for c in label if c.isalpha()]
    return bool(letters) and all(script_of(c) == script for c in letters)


def apply_label_fix(judgments, fixes):
    """Replace the Latin and Greek label of a split answer by the label asked for from its main
    spellings. fixes: {key: (latin, greek)}. Fix pass: the new label is accepted only when it passes the
    five-letter test against the main spellings (contradicts_label) and is in one script each (a Latin
    label all Latin letters, a Greek label all Greek letters). Otherwise the earlier label stays.
    Returns the number of labels that changed."""
    n = 0
    for key, (latin, greek) in fixes.items():
        j = judgments.get(key)
        if not j or not latin:
            continue
        if not _one_script(latin, 'latin') or (greek and not _one_script(greek, 'greek')):
            continue
        if contradicts_label(dict(j, latin=latin, greek=greek or '')):
            continue
        if ei.fold(latin) != ei.fold(j['latin']) or (greek or '') != (j['greek'] or ''):
            n += 1
        j['latin'], j['greek'] = latin, greek or ''
    return n


def still_contradicts(judgments):
    return sorted(k for k, j in judgments.items() if contradicts_label(j))


# ---------------------------------------------------------------- the Greek label of a split (stage 4)

# The key karno was judged Carnutes, with Latin main spellings (Carnotensis) and the Greek label Κάρνοι. Κάρνοι is
# a spelling of the same key that the model gave to another name (Κάρνοις, Κάρνος). No rule over the forms can tell
# that label from Ἀπουλία for Apulia, because the entity has no Greek-script spelling of its own and the label
# agrees with the key. A rule that drops every label whose stem is the stem of a spelling left out of the main forms
# drops 35 labels, about half of them right (Junius, Zenobius, Dardanians), because the model leaves the Greek
# spellings of a name out of main_forms as often as it assigns them to another name. So the model is asked,
# for those cases only, whether the Greek word is the Greek form of the Latin name.

GREEK_FIX_SYSTEM = (
    'You help catalog the proper names found in a corpus of ancient Latin, Greek and English texts. You are given a '
    'Latin name with its type and a description, a Greek word proposed as the Greek form of that name, and lines from '
    'different works that contain Greek spellings of the proposed word. Say whether the Greek word, as these lines '
    'use it, is the Greek name of that Latin name or names something else. Answer with one JSON object and nothing '
    'else, {"answer": "same" or "different"}.')


def greek_candidates(judgments, spellings_of):
    """Keys of old-flow splits whose Greek label should be put to the model: a promotable answer with distinct_names,
    a Greek label, no Greek-script main spelling, and a spelling of the same key outside the main forms whose stem is
    the stem of the label. spellings_of(key) gives every spelling of the key. Returns {key: [those spellings]}."""
    out = {}
    for key, j in judgments.items():
        if 'base' in j or not j.get('greek') or not j.get('distinct_names') or j['type'] not in PROMOTED_TYPES:
            continue
        if any(script_of(f) == 'greek' for f in j['main_forms']):
            continue
        main = {ei.fold(f) for f in j['main_forms']}
        ls = _greek_stem(j['greek'])
        same = [f for f in spellings_of(key) if script_of(f) == 'greek' and ei.fold(f) not in main and _greek_stem(f) == ls]
        if same:
            out[key] = same
    return out


def greek_fix_question(latin, typ, description, greek, snippets):
    lines = [f'Latin name: {latin} ({typ})' + (f', {description}' if description else ''), f'Proposed Greek form: {greek}', 'Lines:']
    for i, (author, lang, text) in enumerate(snippets, 1):
        lines.append(f'{i}. [{author}, {lang}] {text}')
    return '\n'.join(lines)


def parse_greek_fix(text):
    """'same' or 'different' from the reply, or None for an unusable reply."""
    obj = _json_object(text)
    if obj is None:
        return None
    a = str(obj.get('answer') or '').strip().lower()
    return a if a in ('same', 'different') else None


def apply_greek_fix(judgments, fixes):
    """fixes: {key: 'same' | 'different'}. A label the model calls different is removed from the judgment.
    Returns the number of labels removed."""
    n = 0
    for key, v in fixes.items():
        j = judgments.get(key)
        if j and v == 'different' and j.get('greek'):
            j['greek'] = ''
            n += 1
    return n


# ---------------------------------------------------------------- key collisions split by stem (stage 4, fix pass 4b)

# A corpus name is keyed by the first five transliterated letters of a spelling, so two names can share a key
# (massi holds Massilia, Masinissa written Massinissa, and Mount Massicus). The stem test groups the spellings of a
# key by their stem, the folded spelling minus a case ending of the matcher's tables with four letters left at least
# (Fabius, Fabium, Fabio and Fabii are one group). When two or more groups each hold at least COLLISION_MIN_LINES
# lines in at least COLLISION_MIN_WORKS works, the key is a collision candidate and each qualifying group is put to
# the model as a name of its own.
#
# Fix pass 4b. A group becomes a new entity only when the model names it with a promotable type, the name is a
# different entity from the key's earlier name (the heir), the group has MIN_LINES lines in MIN_WORKS works on its
# own, and its stem is not a stem of the heir's main spellings. Everything else stays with the heir, which keeps its
# id, its labels and its description. A key with no heir (its earlier answer was other) promotes the groups that
# pass the same tests.

COLLISION_MIN_LINES = 5
COLLISION_MARK = 'collision'      # entities.homonym_group of a name carved from a key collision
COLLISION_MIN_WORKS = 2


GROUP_STEM_MIN = 4


def group_stem(form):
    """The stem of a spelling: folded, minus a case ending of the matcher's tables (Latin or Greek by script),
    four letters left at least, so that Fabius, Fabium, Fabio and Fabii are one group (five letters would leave
    each of them whole)."""
    f = ei.fold(form)
    ends = ei.GR_END if any('α' <= c <= 'ω' for c in f) else ei.LA_END
    return ei.strip_end(f, ends, GROUP_STEM_MIN)


def collision_groups(rows):
    """rows: (spelling, work, line key) of one corpus name's mentions. Returns {stem: {'forms': {spelling:
    lines}, 'lines': distinct lines of the group, 'works': distinct works, 'work_ids': the works}} for every group."""
    acc = {}
    for form, work, line in rows:
        st = group_stem(form)
        if not st:
            continue
        g = acc.setdefault(st, {'lines': set(), 'works': set(), 'forms': {}})
        g['lines'].add((work, line))
        g['works'].add(work)
        g['forms'].setdefault(form, set()).add((work, line))
    return {st: {'forms': {f: len(v) for f, v in g['forms'].items()}, 'lines': len(g['lines']), 'works': len(g['works']),
                 'work_ids': sorted(g['works'])} for st, g in acc.items()}


def qualifying_groups(groups, min_lines=COLLISION_MIN_LINES, min_works=COLLISION_MIN_WORKS):
    """{stem: group} of the groups with min_lines lines in min_works works."""
    return {st: g for st, g in groups.items() if g['lines'] >= min_lines and g['works'] >= min_works}


def collision_candidate(groups, min_lines=COLLISION_MIN_LINES, min_works=COLLISION_MIN_WORKS):
    """The qualifying groups {stem: group} of a key when at least two qualify, else {}."""
    q = qualifying_groups(groups, min_lines, min_works)
    return q if len(q) >= 2 else {}


def collision_identity(answer):
    """The name a group answer stands for: its folded Latin name when the type is promotable, else None."""
    if not answer or answer['type'] not in PROMOTED_TYPES or not answer.get('latin'):
        return None
    return ei.fold(answer['latin'])


def _distance_within(a, b, limit=2):
    """True when the Levenshtein distance of a and b is at most limit."""
    if abs(len(a) - len(b)) > limit:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return False
        prev = cur
    return prev[-1] <= limit


def same_collision_name(x, y):
    """Two group answers (both promotable) name the same entity when their folded Latin names are equal, or
    when their types are equal and one folded name contains the other or they differ by two letters at most
    (Romani and Romans, Mount Olympus and Olympus). A place and its people are two entities."""
    fx, fy = collision_identity(x), collision_identity(y)
    if fx == fy:
        return True
    if x['type'] != y['type']:
        return False
    return fx in fy or fy in fx or _distance_within(fx, fy, 2)


def _norm_translit(s):
    """Transliteration with the Greek ou written u, so that Καρνούτων and Carnutes can be compared."""
    return ei.translit(s).replace('ou', 'u')


def label_stem_of(label):
    """The transliterated stem of a Latin label: minus a case ending of the Latin table, four letters left at least."""
    t = _norm_translit(label)
    return ei.strip_end(t, ['us', 'um', 'es', 'is', 'os', 'a', 'o', 'e', 'i'], 4)


_HEIR_ENDINGS = ('', 'a', 'an', 'as', 'e', 'en', 'es', 'i', 'in', 'is', 'o', 'oi', 'ois', 'on', 'os', 'ous', 'u', 'um', 'us', 'y', 'ys')


def stays_with_heir(form, heir_label):
    """True for a Greek-script spelling that is the stem of the heir's Latin label plus a case ending (Καρνούτων and
    Καρνούτῳ for Carnutes): it is a Greek form of the heir whatever group the model put it in. A spelling that only
    starts like the label does not count (Ἀβισάρου is not a form of Abisai)."""
    if script_of(form) != 'greek' or not heir_label:
        return False
    stem = label_stem_of(heir_label)
    t = _norm_translit(form)
    return len(stem) >= 5 and t.startswith(stem) and t[len(stem):] in _HEIR_ENDINGS


def _prefix_of_label(stem, label):
    """True when the transliterated group stem (five letters at least) is the start of the transliterated Latin label
    of the heir. Macedonia and Μακεδονία share the stem of Macedonians, so a group of them is not a different name
    from the people of the same name."""
    g = _norm_translit(stem)
    return len(g) >= 5 and _norm_translit(label).startswith(g)


def collision_judgments(judgments, candidates, answers, log=print, min_lines=10, min_works=3):
    """Carve the names the model finds in the groups of a collision key out of the key, and leave the rest.
    candidates: {key: {stem: group}} for every group of the key (collision_groups, with the spellings in 'forms').
    answers: {key: {stem: answer dict or None}}. A group is carved when the model names it with a promotable
    type (collision_identity), the name is a different entity from the earlier name of the key
    (same_collision_name is false), the groups that name one entity together hold min_lines lines in min_works
    works, and no stem of the heir's main spellings is the group's stem. The earlier judgment of the key, the heir,
    stays: it keeps its id, labels and description, loses the carved spellings from its main forms, and loses its
    Greek label only when that label is a carved spelling. A Greek spelling with the stem of the heir's Latin label
    stays with the heir. A key with no promotable earlier answer carves the groups that pass the same tests.
    Returns (judgments, report)."""
    out = dict(judgments)
    rep = {'candidates': 0, 'asked_groups': 0, 'split': 0, 'not_split': 0, 'names': 0, 'keys': {}}
    used = set(out)
    for key, groups in sorted(candidates.items()):
        qual = qualifying_groups(groups)
        if len(qual) < 2:
            continue
        rep['candidates'] += 1
        ans = answers.get(key, {})
        rep['asked_groups'] += sum(1 for st in qual if st in ans)
        old = out.get(key)
        heir = old if old and collision_identity(old) else None
        heir_main = {group_stem(f) for f in old['main_forms']} if heir and old.get('distinct_names') else set()
        named = []
        for st in sorted(qual, key=lambda st: (-qual[st]['lines'], st)):
            a = ans.get(st)
            if not collision_identity(a):
                continue
            if heir and (same_collision_name(heir, a) or st in heir_main or _prefix_of_label(st, heir['latin'])):
                continue
            named.append(st)
        clusters = []
        for st in named:
            for cl in clusters:
                if same_collision_name(ans[cl[0]], ans[st]):
                    cl.append(st)
                    break
            else:
                clusters.append([st])
        carve = []
        for cl in clusters:
            lines = sum(groups[st]['lines'] for st in cl)
            works = len({w for st in cl for w in groups[st].get('work_ids', [])}) or sum(groups[st]['works'] for st in cl)
            if lines >= min_lines and works >= min_works:
                carve.append(cl)
        if not carve:
            rep['not_split'] += 1
            continue
        rep['split'] += 1
        taken_all = {}
        for cl in carve:
            for st in cl:
                for f in groups[st]['forms']:
                    taken_all[f] = id(cl)
        heir_label = heir['latin'] if heir else None
        made = []
        carved_forms = set()
        for cl in carve:
            a = ans[cl[0]]
            forms = {f for st in cl for f in groups[st]['forms']}
            keep = {f for f in forms if stays_with_heir(f, heir_label)}
            forms -= keep
            if not forms:
                continue
            carved_forms |= forms
            others = {ei.fold(f) for c2 in carve if c2 is not cl for st in c2 for f in groups[st]['forms']}
            labels = [ans[st]['greek'] for st in cl if ans[st].get('greek')]
            labels = list(dict.fromkeys(g for g in labels if ei.fold(g) not in others))
            top = cl[0]
            vkey = top if len(top) >= 6 else f'{top}2'
            while vkey in used:
                vkey += '2'
            used.add(vkey)
            out[vkey] = {'type': a['type'], 'latin': a['latin'], 'greek': labels[0] if labels else '',
                         'description': a.get('description') or '', 'distinct_names': True, 'main_forms': sorted(forms),
                         'base': key, 'greek_alternatives': labels[1:]}
            made.append({'key': vkey, 'latin': a['latin'], 'type': a['type'], 'groups': sorted(cl),
                         'lines': sum(groups[st]['lines'] for st in cl), 'kept_with_heir': sorted(keep)})
            rep['names'] += 1
        if not made:
            rep['split'] -= 1
            rep['not_split'] += 1
            continue
        if heir:
            j = dict(heir)
            all_forms = {f for g in groups.values() for f in g['forms']}
            # the heir's Greek label is tested against the spellings it had before the carve, as the installed store did
            j['label_forms'] = sorted(all_forms) if not heir.get('distinct_names') else list(heir['main_forms'])
            if j.get('distinct_names'):
                j['main_forms'] = [f for f in j['main_forms'] if f not in carved_forms]
            else:
                j['distinct_names'] = True
                j['main_forms'] = sorted(all_forms - carved_forms)
            if j.get('greek') and ei.fold(j['greek']) in {ei.fold(f) for f in carved_forms}:
                j['greek'] = ''
            out[key] = j
        heir_lines = sum(g['lines'] for st, g in groups.items() if not any(f in carved_forms for f in g['forms'])) if heir else None
        rep['keys'][key] = {'heir': heir['latin'] if heir else None,
                            'groups': {st: {'lines': g['lines'], 'works': g['works'],
                                            'forms': sorted(g['forms'], key=lambda f: -g['forms'][f])[:6],
                                            'identity': collision_identity(ans.get(st))} for st, g in groups.items()},
                            'heir_lines_kept': heir_lines, 'names': made}
    log(f"collisions: {rep['candidates']} candidates, {rep['split']} split into {rep['names']} names, "
        f"{rep['not_split']} not split")
    return out, rep


# ---------------------------------------------------------------- the label of a merged group

# A group of promoted entities merged by dedupe_promoted takes its label by the heading rule of the
# corpus names (a nominative-looking Latin form first, then the most lines), not from the surviving key.
# 'ae' is added to the strong endings for this choice: it is the nominative plural of a first-declension
# place name (Baiae, Athenae), against the accusative plural -as of the same name.
GROUP_LA_STRONG = LA_STRONG + ('ae',)


def group_rank(label, script, place=False):
    f = _plain(label)
    if place and is_demonym(label, script):
        return 3
    if script == 'latin':
        strong, weak = GROUP_LA_STRONG, LA_WEAK
    else:
        strong, weak = tuple(_plain(x) for x in GR_STRONG), tuple(_plain(x) for x in GR_WEAK)
    if f.endswith(strong):
        return 0
    return 1 if f.endswith(weak) else 2


def pick_group_label(cands, script, place=False):
    """cands: [(label, lines)]. The nominative-looking label with the most lines. For a place type
    (stage 4) a demonym label ranks below every place-name label."""
    cands = [(lab, n) for lab, n in cands if lab]
    if not cands:
        return None
    return min(cands, key=lambda c: (group_rank(c[0], script, place), -c[1], c[0]))[0]


# ---------------------------------------------------------------- duplicates among promoted entities

def single_letters(label):
    """The transliterated label with each run of one doubled letter written once (massinisa for Massinissa)."""
    return re.sub(r'(.)\1+', r'\1', ei.translit(label))


def dedupe_promoted(db, log=print):
    """Merge promoted entities that share a type and a folded Latin label, or whose Latin label
    equals another's Greek label after the names transliteration. The survivor is the one with
    the most lines. Every key stays in entity_aliases, forms, mentions and documents are united."""
    lines = {}
    for (eid, _lang), n in extras.line_counts(db).items():
        lines[eid] = lines.get(eid, 0) + n
    ents = {}
    for eid, entity_id, typ, label, mark in db.execute(
            "select eid, entity_id, type, label, homonym_group from entities where source = 'promoted'"):
        ents[eid] = {'id': entity_id, 'type': typ, 'label': label, 'greek': None, 'carved': mark == COLLISION_MARK}
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

    first, by_trans, by_single = {}, {}, {}
    for eid, e in ents.items():
        first.setdefault((e['type'], ei.fold(e['label'])), []).append(eid)
        by_trans.setdefault((e['type'], ei.translit(e['label'])), []).append(eid)
        by_single.setdefault((e['type'], single_letters(e['label'])), []).append(eid)
    for grp in first.values():
        for x in grp[1:]:
            union(grp[0], x)
    # stage 4: a name carved from a key collision joins the promoted entity of the same type whose label is the
    # same name with doubled letters written single (Massinissa and Masinissa)
    for grp in by_single.values():
        if len(grp) > 1 and any(ents[x]['carved'] for x in grp):
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
        # fix pass 4b: a name carved from a collision never changes the survivor or the labels of an entity that was
        # promoted before (the installed store), it only adds its mentions and spellings
        older = [m for m in members if not ents[m]['carved']]
        surv = max(older or members, key=lambda e: (lines.get(e, 0), -e))
        rep['groups'] += 1
        # stage 3b: the group's labels come from the heading rule, not from the surviving key
        lat_cands = [(ents[m]['label'], lines.get(m, 0)) for m in (older or members)]
        orig_grc = ents[surv]['greek']
        grc_cands = [(ents[m]['greek'], lines.get(m, 0)) for m in (older or members) if ents[m]['greek']]
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
            db.execute('delete from entity_labels where eid = ?', (other,))
            db.execute('delete from entities where eid = ?', (other,))
            rep['merged_away'] += 1
        forms_now = [f for (f,) in db.execute('select form from variants where eid = ?', (surv,))]
        is_place = ents[surv]['type'] in PLACE_TYPES
        best_la = pick_group_label(lat_cands, 'latin', is_place) or ents[surv]['label']
        has_carved = len(older) < len(members)
        best_grc = pick_group_label([(g, n) for g, n in grc_cands if has_carved or greek_label_ok(g, forms_now)], 'greek', is_place)
        if best_la != ents[surv]['label']:
            rep['labels_changed'] = rep.get('labels_changed', 0) + 1
            rep.setdefault('label_change_examples', []).append({'was': ents[surv]['label'], 'now': best_la,
                                                                'kept': ents[surv]['id'], 'type': ents[surv]['type']})
            db.execute('update entities set label = ? where eid = ?', (best_la, surv))
            db.execute('update entity_labels set display_label = ?, display_label_la = ? where eid = ?',
                       (best_la, best_la, surv))
            lf = ei.fold(best_la)
            if lf and not db.execute('select 1 from variants where eid = ? and form = ?', (surv, lf)).fetchone():
                db.execute('insert into variants values (?,?,?,?,?)', (surv, lf, '', 'form', 'promoted'))
        db.execute('update entity_labels set display_label_grc = ? where eid = ?', (best_grc, surv))
        if best_grc != orig_grc:
            rep['greek_changed'] = rep.get('greek_changed', 0) + 1
            if orig_grc and not best_grc:
                rep['greek_dropped_in_groups'] = rep.get('greek_dropped_in_groups', 0) + 1
                rep.setdefault('greek_dropped_group_examples', []).append({'label': best_la, 'greek': orig_grc})
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
