"""Entity mentions, merge pass 4d (2026-10-19): put back together the names that the stage 4 carve split
from one referent.

The carve of a key collision (backend/entity_promote.py, collision_judgments) makes a new entity for each
name it finds beside the entity the key came from. Reading 60 of the 893 split keys, 11 carved one referent
in two: a case form (Nerea, the accusative of Nereus), a spelling or script (Tyrii and Tyrians), a people
under another word (Iberi, Christicolae), or a place beside its own adjective (Ephesius, Gordyene).

Two layers decide, a carved entity against the entity it was carved from (the parent) or against another
carved entity of the same key:

    layer 1, no model. same_stem(): at least 80 percent of the carved name's mention rows are spellings that
        are case forms of a heading of the parent (case_form_of: the heading's stem, four letters at least, plus
        an ending of its declension, after the Greek is written in Latin letters), or, between two peoples,
        the same stem under the Latin and English people endings (Tyrii, Tyrians). A heading in -a takes no
        ending in -us (Julia is not Julius) and a place is not a case form of a people. The same type is
        required, except for the Greek -eus names (Nereus, Nerea).
    layer 2, the model. merge_question() and parse_answer(): SAME, DIFFERENT or UNCLEAR, merged on SAME only,
        except that kind_veto() keeps apart a place and its inhabitants, or a person and a people, when fewer
        than a fifth of the carved rows are case forms of a heading.

apply_merge() moves the carved entity's spellings, mention rows, document rows, search names and aliases
into the survivor and removes it. apply_partial() does the same for the spellings of a carved name that the
build had merged into an older entity (the entity stays). Nothing here reads the gateway address or the key.
"""
import json
import re

from backend import entity_index as ei
from backend import entity_promote as pr


MIN_STEM = 4            # letters left after an ending is cut
MIN_STEM_PEOPLE = 3     # two peoples (Tyrii and Tyrians)
SHARE = 0.8             # the share of a carved entity's mention rows whose spelling must match


def _norm(form):
    """A spelling folded, Greek written in Latin letters, and the pairs the two alphabets spell differently
    collapsed (spec table: k and c, y and u, ai and ae, oi and oe, ou and u, ch and kh, ph and f, th and t,
    an initial rh and r, ei and i)."""
    t = ei.translit(ei.fold(form))
    t = t.replace('ou', 'u').replace('ei', 'i')
    if t.startswith('rh'):
        t = t[1:]
    return t


def _n(*ends):
    return frozenset(_norm(e) for e in ends)


# The case endings of a name by the ending of its heading (normalized). A carved spelling is a case form of the
# heading when it is the heading's stem plus one of these. A heading with an ending of none of these lists has no
# case forms (Sidon is declined in the third declension, so Sidonii and Sidonians are other words).
# Longest heading ending first.
_PARADIGMS = [
    ('eus', _n('eus', 'ea', 'eos', 'ei', 'eo', 'eum', 'eu', 'ei', 'e')),                  # Nereus: Nerea, Nereos
    ('us', _n('us', 'i', 'o', 'um', 'e', 'os', 'orum', 'is', 'on', 'oi', 'u', 'ois', 'ous', 'ou')),
    ('os', _n('us', 'i', 'o', 'um', 'e', 'os', 'orum', 'is', 'on', 'oi', 'u', 'ois', 'ous', 'ou')),
    ('um', _n('um', 'i', 'o', 'a', 'orum', 'is', 'on', 'us')),
    ('on', _n('um', 'i', 'o', 'a', 'orum', 'is', 'on', 'u')),
    ('es', _n('es', 'um', 'ibus', 'as', 'is', 'em', 'e', 'i', 'a', 'on', 'ai')),
    ('a', _n('a', 'ae', 'am', 'as', 'arum', 'is', 'e', 'an', 'es', 'ai', 'ais')),
    ('e', _n('a', 'ae', 'am', 'as', 'arum', 'is', 'e', 'an', 'es', 'ai', 'ais')),
    ('oi', _n('oi', 'on', 'ois', 'oisi', 'oisin', 'ous', 'u')),
    ('ii', _n('ii', 'iorum', 'iis', 'ios', 'ius', 'i', 'orum', 'is', 'os')),
    ('i', _n('i', 'orum', 'is', 'os', 'ii')),
    ('is', _n('is', 'i', 'em', 'e', 'es', 'um', 'ibus', 'idos', 'ida', 'idis')),
    ('', _n('', 'is', 'i', 'em', 'e', 'es', 'um', 'ibus', 'os', 'a', 'ai', 'ae', 'on', 'u')),
]
# English people endings, used only between two peoples (Tyrii, Tyrians) and with the Latin plural endings
_PEOPLE_ENDINGS = sorted(_n('ians', 'ans', 'ites', 'ite', 'ian', 'an', 'eans', 'ese', 'ii', 'i', 'es', 'ae', 'oi', 'ioi',
                                        'ios', 'io', 'iorum', 'iis', 'ium', 'ius', 'ia', 'ion', 'ois', 'ous', 'orum', 'os', 'is', 'um', 'us', 'on',
                                        'iu', 'u', 'ias', 'iam', 'as', 'am', 'a', 'e', 'o') - {''},
                         key=len, reverse=True)


def case_family(heading):
    """(stem, endings, heading ending) of a heading: its stem and the endings of its case forms. The longest
    heading ending of the table that leaves four letters (three before -eus), else the heading itself with the
    endings of a name with none."""
    t = _norm(heading)
    for end, fam in _PARADIGMS:
        if end and t.endswith(end) and len(t) - len(end) >= MIN_STEM - (1 if end == 'eus' else 0):
            return t[:-len(end)], fam, end
    return t, dict(_PARADIGMS)[''], ''


_GREEK_LETTER = re.compile('[\u0370-\u03ff\u1f00-\u1fff]')
_LATIN_ONLY = _n('am', 'arum', 'orum', 'ibus')
_GREEK_ONLY = _n('an', 'ais', 'oi', 'ois', 'oisi', 'oisin', 'ous')


def case_form_of(form, headings):
    """The ending of the heading when the spelling is one of its case forms (Greek or Latin, any script), else
    None. A Latin spelling takes no Greek-only ending (Sparta, Spartan) and a Greek one no Latin-only ending,
    and a Latin spelling in -oe or -oi is not the Greek plural -oi (Alcathoe is not Alcathous)."""
    t = _norm(form)
    greek = bool(_GREEK_LETTER.search(str(form)))
    for h in headings:
        stem, fam, end = case_family(h)
        rest = t[len(stem):]
        if len(stem) >= MIN_STEM - 1 and t.startswith(stem) and rest in fam:
            if (not greek and rest in _GREEK_ONLY) or (greek and rest in _LATIN_ONLY):
                continue
            if greek and rest == 'is' and end in ('a', 'e'):
                continue         # Greek -eis is not a case form of a first-declension name (Phokaia, Phokaieis)
            return end
    return None


def people_stem(form):
    t = _norm(form)
    for e in _PEOPLE_ENDINGS:
        if t.endswith(e) and len(t) - len(e) >= MIN_STEM_PEOPLE:
            return t[:-len(e)]
    return t


def same_stem(parent_headings, carved_forms, parent_type=None, carved_type=None, parent_forms=()):
    """True when the carved spellings are case forms of a heading of the parent (its Latin and Greek labels:
    Nerea of Nereus), or the people name in another word (Tyrii for Tyrians) when both are peoples.
    carved_forms: {spelling: mention rows}. At least SHARE of the carved rows must be such a spelling. A
    stem of the heading must have four letters (three for a case form of a stem in -e: Nereus, Nerea)."""
    total = sum(carved_forms.values())
    if not total:
        return False
    both_peoples = parent_type == 'people' and carved_type == 'people'
    pstems = {people_stem(h) for h in list(parent_headings) + list(parent_forms)} if both_peoples else set()
    hit = 0
    for form, n in carved_forms.items():
        end = case_form_of(form, parent_headings)
        if end is not None and (parent_type == carved_type or end == 'eus') and 'people' not in (parent_type, carved_type):
            hit += n
        elif both_peoples and people_stem(form) in pstems:
            hit += n
    return hit >= SHARE * total


# ---------------------------------------------------------------- the model's question

MERGE_SYSTEM = (
    'You check the work of a program that sorts the spellings of ancient proper names into entities. The program '
    'found that one name key held spellings of more than one name and cut some spellings out of entity A into a '
    'new entity B. Sometimes the cut was wrong because B is the same person, people or place as A. You see A '
    'and B, each with its spellings and up to three lines from different works, the spelling marked between the '
    'signs \u27e6 \u27e7. Answer SAME when B is A written another way: a case form of A\'s name (Hectora, the '
    'accusative of Hector), a spelling, transliteration or script variant (Marseille and Massilia, a Latin name '
    'and its Greek form), the same people in a Latin, a Greek or an English word, the singular, the plural or the '
    'adjective of A\'s own people or land (Persae and Persians, a Persian man, the Cilician plain beside Cilicia), or B holds spellings of A\'s own name (the last line lists the spellings of B that are case forms of a heading of A; when it lists most of B\'s spellings, answer SAME). Answer '
    'DIFFERENT when B is another person, place, god or people even if the spellings look alike (Valeria and '
    'Valerius, Atlas the god and Atlas the mountains). A place and its inhabitants are DIFFERENT names, and so are a person and the family or people of the same '
    'name (Julius and the Julii), however the lines read, unless B holds spellings of A\'s own name (Sparta and the Spartans, Rhodes and the Rhodians). '
    'Answer UNCLEAR only when the lines do not allow a decision. Answer with one JSON object and nothing else, '
    '{"answer": "SAME" or "DIFFERENT" or "UNCLEAR", "reason": "at most twenty words"}.')


MERGE_CONFIRM_SYSTEM = (
    'You check the work of a program that sorts the spellings of ancient proper names into entities. The program cut '
    'some spellings out of entity A into a new entity B. A first reader said B is the same person, people or place '
    'as A, and that B should be merged back. You see A and B, each with its spellings and up to three lines from '
    'different works, the spelling marked between the signs \u27e6 \u27e7. Look for a reason the first reader is wrong: '
    'B may be another person, place, people or god with a similar name, a place beside its inhabitants, a person '
    'beside a family or a people of the same name, a person beside a place named after him, or a god beside an '
    'epithet. Answer DIFFERENT if you find such a reason in the lines. Answer SAME only if the lines show that B is '
    'A written another way: a case form, a spelling or script variant, the same people in another word, the adjective '
    'or singular of A\'s own people or land, or B holds spellings of A\'s own name. Answer UNCLEAR when the lines do '
    'not allow a decision. Answer with one JSON object and nothing else, {"answer": "SAME" or "DIFFERENT" or '
    '"UNCLEAR", "reason": "at most twenty words"}.')


def merge_question(a, b):
    """The prompt for entity a (the one that keeps its name) and entity b (the carved name). Each is a dict
    with label, type, description, greek, forms [(spelling, rows)], lines [text], listed [spelling], and for
    a the headings the case forms are cut from. A last line says which spellings of b are case forms of a
    heading of a (case_form_of), so the model need not parse the endings."""
    out = []
    for tag, e in (('A', a), ('B', b)):
        head = f"Entity {tag}: {e['label']} ({e['type']})"
        if e.get('greek'):
            head += f", Greek {e['greek']}"
        if e.get('description'):
            head += f", {e['description']}"
        out.append(head)
        out.append('Spellings in the corpus: ' + ', '.join(f'{f} ({n})' for f, n in e['forms'][:10]))
        if tag == 'A' and e.get('listed'):
            out.append('Other listed spellings: ' + ', '.join(sorted(set(e['listed']))[:12]))
        for ln in e.get('lines', []):
            out.append('  ' + ln)
    hits = heading_case_forms(a, b)
    out.append("Spellings of B that are case forms of a heading of A: " + (', '.join(hits) if hits else 'none'))
    return '\n'.join(out)


def heading_case_forms(a, b):
    """The spellings of b (up to ten, most frequent first) that are case forms of a heading of a."""
    heads = a.get('headings') or [x for x in (a['label'], a.get('greek'), a.get('latin')) if x]
    return [f for f, _n in b['forms'][:10] if case_form_of(f, heads)]


SHARE_KIND = 0.2      # the share of b's mention rows that must be case forms of a heading of a, to merge across kinds


def case_form_share(a, b):
    """The share of b's mention rows whose spelling is a case form of a heading of a."""
    heads = a.get('headings') or [x for x in (a['label'], a.get('greek'), a.get('latin')) if x]
    total = sum(n for _f, n in b['forms'])
    return sum(n for f, n in b['forms'] if case_form_of(f, heads)) / total if total else 0.0


_KIND = {'place': 'place', 'people': 'people', 'person': 'person'}


def kind_veto(a, b):
    """True when a model answer SAME must not merge: a place and its inhabitants, or a person and a people, that
    hold fewer than a fifth of their rows in case forms of a heading (Fidenae and Fidenates).
    These are the pairs the model reads as one referent although the names are two (the split sample's RIGHT
    keys), so the rule that the model answers SAME on its own is not enough for them."""
    ka, kb = _KIND.get(a['type']), _KIND.get(b['type'])
    if not ka or not kb or ka == kb:
        return False
    if {ka, kb} not in ({'place', 'people'}, {'person', 'people'}):
        return False
    return case_form_share(a, b) < SHARE_KIND


def parse_answer(text):
    """('SAME'|'DIFFERENT'|'UNCLEAR', reason) from the reply, or (None, text) when it cannot be read."""
    m = re.search(r'\{.*\}', text or '', re.S)
    if m:
        try:
            o = json.loads(m.group(0))
            v = str(o.get('answer', o.get('verdict', ''))).strip().upper()
            if v in ('SAME', 'DIFFERENT', 'UNCLEAR'):
                return v, str(o.get('reason', ''))
        except ValueError:
            pass
    return None, text


# ---------------------------------------------------------------- the merge

def apply_merge(db, src, dst, rule):
    """Move carved entity `src` into `dst`: mention rows and document rows (a row dst already has for the
    window and spelling is dropped), spellings, model search names, aliases. The survivor keeps its heading,
    labels and description. src is removed, its id stays an alias of dst. Returns
    {'moved': rows moved, 'dropped': rows already there, 'forms': spellings added}."""
    row = db.execute('select entity_id, label, type from entities where eid = ?', (src,)).fetchone()
    moved, dropped = pr._move_rows(db, src, dst, None)
    have = {f for (f,) in db.execute('select form from variants where eid = ?', (dst,))}
    add = [(dst, f, lang, role, source) for f, lang, role, source in
           db.execute('select form, language, role, source from variants where eid = ?', (src,)).fetchall()
           if f not in have]
    db.executemany('insert into variants values (?,?,?,?,?)', add)
    db.execute('delete from variants where eid = ?', (src,))
    if db.execute("select 1 from sqlite_master where name = 'search_names'").fetchone():
        names = {n for (n,) in db.execute("select name from search_names where eid = ? and source = 'model'", (dst,))}
        for n in [n for (n,) in db.execute("select name from search_names where eid = ? and source = 'model'", (src,))]:
            if n not in names:
                db.execute("insert into search_names values (?,?,'model')", (dst, n))
                names.add(n)
        db.execute('delete from search_names where eid = ?', (src,))
    db.execute('update entity_aliases set eid = ? where eid = ?', (dst, src))
    db.execute('insert into entity_aliases values (?,?,?,?,?)', (dst, row[0], row[1], row[2], rule))
    db.execute('delete from entity_labels where eid = ?', (src,))
    db.execute('delete from entity_merges where eid = ?', (src,))
    db.execute('delete from entities where eid = ?', (src,))
    pr._refresh_windows(db, [dst])
    return {'moved': moved, 'dropped': dropped, 'forms': len(add)}


def apply_partial(db, host, dst, forms):
    """Move the rows of the spellings `forms` (a carved name that the build merged into an older entity) from
    `host` to `dst`, with the host's listed spellings that are those forms. The host stays. Returns the same
    counts as apply_merge."""
    folds = {ei.fold(f) for f in forms}
    moved, dropped = pr._move_rows(db, host, dst, folds)
    have = {f for (f,) in db.execute('select form from variants where eid = ?', (dst,))}
    rows = [(rowid, f, lang, role, source) for rowid, f, lang, role, source in
            db.execute('select rowid, form, language, role, source from variants where eid = ?', (host,)).fetchall()
            if ei.fold(f) in folds]
    add = [(dst, f, lang, role, source) for _r, f, lang, role, source in rows if f not in have]
    db.executemany('insert into variants values (?,?,?,?,?)', add)
    db.executemany('delete from variants where rowid = ?', [(r[0],) for r in rows])
    pr._refresh_windows(db, [host, dst])
    return {'moved': moved, 'dropped': dropped, 'forms': len(add)}
