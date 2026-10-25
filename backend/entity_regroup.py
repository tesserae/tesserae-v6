"""People & Places regroup (2026-10-21): take spellings of a different name out of an entry.

The first build grouped the spellings a corpus scan found under an entity by the first five letters of a
name. Stage 4 (entity_promote.collision_judgments) and merge pass 4d (entity_mergeback) repaired only part of
that, so many entries still list spellings of another name (Ἑκαταῖος under Echecrates, Leuconoe under Leucon).

Layer 1, no model: belongs() and layer1(). A spelling belongs to its entity when, folded, with the lunate
sigma and a Latin enclitic taken off, it equals or is a case form (entity_mergeback.case_form_of) of a heading
of the entity, or of a spelling already accepted (repeated until nothing changes). The rest are candidates,
grouped by (entity, stem of the spelling).
Layer 2, the model: question(), parse_answer() and the cache. Apply: apply_moves().
The heading set (headings()) leaves out the model's search names, the alias labels and the spellings the
build itself listed, because the wrong spellings are written into those (the search names of Echecrates hold
Hecataeus). A Greek label counts only when it is a case form of a Latin heading or the entry has no Latin one.
Nothing here reads the gateway address or the key.
"""
import re
import sqlite3
import unicodedata

from backend import entity_extras as ex
from backend import entity_index as ei
from backend import entity_mergeback as mb
from backend import entity_promote as pr

PROTECTED_IDS = ('nm:lauin:main', 'pl:393444')
PROTECTED_PREFIXES = ('pn:lauinia', 'nm:lauinia', 'pn:lauinium', 'nm:lauinium')
_HEBREW = re.compile('[\u0590-\u05ff]')
_GREEK = re.compile('[Ͱ-Ͽἀ-῿]')


def protected(entity_id):
    return entity_id in PROTECTED_IDS or str(entity_id).startswith(PROTECTED_PREFIXES)


_BREAK_MARKS = re.compile(r'[|¦]|(?<=\w)[-\u2010\u2011]\s+(?=\w)')


def prep(s):
    """A spelling made ready for comparison: the lunate sigma written as sigma (the fold keeps it apart), every
    combining mark removed (the Hebrew accent marks U+0591 to U+05C7 and the vowel points as well as the Greek
    breathings and accents, Unicode category Mn, third pass 2026-10-24), and a line-break mark taken out
    (Anton|ino, Anton- ino)."""
    s = str(s or '').replace('ϲ', 'σ').replace('Ϲ', 'Σ')
    s = _BREAK_MARKS.sub('', s)
    return unicodedata.normalize('NFC', ''.join(c for c in unicodedata.normalize('NFD', s)
                                                if unicodedata.category(c) != 'Mn'))


def _is_greek(s):
    return bool(_GREEK.search(s))


def _is_latin_or_greek(s):
    return bool(re.search('[A-Za-z\u00c0-\u024f]', s)) or _is_greek(s)


def headings(db, eid):
    """The heading strings of an entity: label, display labels (the Greek one under the rule in the module
    docstring), and for list and promoted entities the spellings the lists gave (variants of source 'list' or
    'promoted')."""
    heads = set()
    mt = db.execute('select list_eid from entity_merges where eid = ?', (eid,)).fetchone()
    for e in (eid, mt[0]) if mt else (eid,):
        heads |= _own_headings(db, e)
    return {h for h in heads if ei.fold(h)}


def _own_headings(db, eid):
    row = db.execute('select label from entities where eid = ?', (eid,)).fetchone()
    heads = {prep(row[0])} if row and row[0] else set()
    lab = db.execute('select display_label, display_label_la, display_label_grc from entity_labels where eid = ?',
                     (eid,)).fetchone()
    latin = set(heads)
    if lab:
        for x in lab[:2]:
            if x:
                heads.add(prep(x))
                latin.add(prep(x))
    latin = {h for h in latin if not _is_greek(h)}
    if lab and lab[2]:
        g = prep(lab[2])
        if not latin or mb.case_form_of(g, list(latin)) is not None:
            heads.add(g)
    for (f,) in db.execute("select form from variants where eid = ? and source in ('list', 'promoted')", (eid,)):
        heads.add(prep(f))
    key = db.execute('select name_key from entities where eid = ?', (eid,)).fetchone()
    if key and key[0] and not _is_latin_or_greek(key[0]):
        heads.add(prep(key[0]))      # a Hebrew or other non-Greek, non-Latin name whose entry was built on that spelling (Adonai)
    return heads


_AS_FIRST = frozenset(mb._n('a', 'ae', 'am', 'an', 'ai', 'as', 'e', 'en'))
_AS_THIRD = frozenset(mb._n('a', 'os', 'i', 'em', 'es', 'ibus', 'um', 'on', 'is', 'u', 'ou', 'oi', 'ai', 'an', 'es'))


class Family:
    """The heading strings of one entity, indexed by case stem so that a spelling is tested only against the
    headings whose stem begins it."""

    def __init__(self, heads=()):
        self.by_stem = {}
        self.folded = set()
        self.raw = set()          # headings in a script the transliteration does not read (Hebrew): compared by the fold
        self.stems_as = set()
        for h in sorted(heads):
            self.add(h)

    def add(self, h):
        stem = mb.case_family(h)[0]
        lst = self.by_stem.setdefault(stem, [])
        if h not in lst:
            lst.append(h)
        self.folded.add(mb._norm(h))
        n = mb._norm(h)
        if not n:
            self.raw.add(ei.fold(h))
        if n.endswith('as') and len(n) >= 5:
            self.stems_as.add(n[:-2])

    def matches_as(self, t):
        """A heading in -as (Aeneas, Acragas) takes the Greek accusative in -an (Aenean) and, in the third
        declension, the stem in -nt (Acragantem, \u1f08\u03ba\u03c1\u03ac\u03b3\u03b1\u03bd\u03c4\u03b1)."""
        for st in self.stems_as:
            if t.startswith(st):
                rest = t[len(st):]
                if rest in _AS_FIRST or (rest.startswith('nt') and rest[2:] in _AS_THIRD):
                    return True
        return False

    def matches(self, form):
        t = mb._norm(form)
        if not t and _HEBREW.search(form):
            return ei.fold(form) in self.raw          # Hebrew: the same word once its marks are gone
        if t in self.folded or self.matches_as(t):
            return True
        heads = []
        for n in range(max(3, 1), len(t) + 1):
            heads += self.by_stem.get(t[:n], ())
        return bool(heads) and mb.case_form_of(form, heads) is not None


def belongs(form, fam):
    """True when the spelling (or the spelling without its enclitic) equals or is a case form of a heading."""
    form = prep(form)
    if fam.matches(form):
        return True
    base, enc = ex.without_enclitic(form)
    if base and fam.matches(base):
        return True
    f = ei.fold(form)
    if len(f) > 6 and f.endswith('en') and not _is_greek(f):
        return any(fam.matches(f[:-2] + e) for e in ('a', 'e'))      # Atalanten, Iordanen: the Greek accusative
    return False


# Derivational suffixes (third pass 2026-10-24), as the cores of the fold's Latin letters (ae is written ai, c is k,
# ei is i): -aeus, -eus, -ianus, -inus, -ides, -ensis and -enses, -itis, -icus, -anus, -ates, the diminutives -ulus
# -olus -ellus, and the Greek shapes -aios, -eios, -ianos, -inos, -ides, -ikos. A name that goes on with one of them
# is another name (Hecataeus from Hecate, Maximinus from Maximianus, Graeculus from Graeci), not a case form.
_DERIV_CORES = ('ai', 'ian', 'in', 'id', 'ens', 'it', 'ik', 'an', 'at')
_DERIV_EXTRA = ('ul', 'ol', 'ell')       # the diminutives -ulus -olus -ellus, used only to tell two whole names apart
_NOMINAL_ENDS = ('orum', 'arum', 'ibus', 'ois', 'us', 'um', 'os', 'is', 'es', 'em', 'am', 'as', 'ae', 'ai', 'i', 'o', 'e', 'a', 'u')
_PATRONYMIC_ENDS = ('es', 'ae', 'as')    # -ides, -idae: the third-declension forms of a name in -is (Tiberidi) are not derived


def derivational_core(rest, cores=_DERIV_CORES):
    """The derivational suffix core (see _DERIV_CORES) that the letters `rest` end in once one nominal case ending
    is taken off (a bare ending, a stem with no ending, or a Greek accusative -an or -en count for none), else ''."""
    for end in _NOMINAL_ENDS:
        if not rest.endswith(end) or len(rest) == len(end):
            continue
        core = rest[:len(rest) - len(end)]
        for c in sorted(cores, key=len, reverse=True):
            if core.endswith(c) and (c != 'id' or end in _PATRONYMIC_ENDS):
                return c
    return ''


_NOMINATIVE = ('us', 'os', 'is', 'es', 'eus', '')


def word_suffix(form):
    """The derivational suffix core of a spelling taken as a nominative (Hecataeus: ai, Maximinus: in, Maximianus:
    ian, Graeculus: ul), else ''. A heading that ends as a first declension or a Latin or Greek e/a/i name (Hecate,
    Graeci) has none."""
    f = prep(form)
    base, _enc = ex.without_enclitic(f)
    stem, _fam, end = mb.case_family(base or f)
    if end not in _NOMINATIVE:
        return ''
    for c in sorted(_DERIV_CORES + _DERIV_EXTRA, key=len, reverse=True):
        if stem.endswith(c) and len(stem) > len(c):
            return c
    return ''


def derivational_of(form, fam):
    """True when the spelling goes on from the stem of a heading of `fam` with a derivational suffix (Hecataeus
    from Hecate: stem hekat, rest aius), and the rest is not one of the heading's own case endings."""
    t = mb._norm(prep(form))
    base, _enc = ex.without_enclitic(prep(form))
    ts = [t] + ([mb._norm(base)] if base else [])
    for t in ts:
        for n in range(3, len(t)):
            for h in fam.by_stem.get(t[:n], ()):
                stem, endings, _end = mb.case_family(h)
                rest = t[len(stem):]
                if rest and rest not in endings and derivational_core(rest):
                    return True
    return False


def _broken_completion(db, lines, eid, form, fam):
    """True when the spelling is the front of a word broken across a line (Anton-  inus in the source, Anton|ino in
    a reading text) whose whole word belongs to the entry. Checked only for a spelling that begins a longer heading
    spelling, and on up to six of its mention rows."""
    if lines is None:
        return False
    f = ei.fold(prep(form))
    if len(f) < 3 or not any(h.startswith(f) and len(h) > len(f) for h in fam.folded):
        return False
    rows = db.execute('select w.window_id, m.line_ref, w.work from mention_rows m join windows w using(wid) '
                      'where m.eid = ? and m.form = ? limit 6', (eid, form)).fetchall()
    if not rows:
        return False
    pat = re.compile(re.escape(form) + r'\s*[-|\u00a6\u2010\u2011]\s*(\w+)')
    done = 0
    for wid, ref, work in rows:
        r = lines.db.execute('select text from window_texts where id = ?', (wid,)).fetchone()
        m = pat.search(r[0]) if r and r[0] else None
        if not m or not fam.matches(form + m.group(1)):
            return False
        done += 1
    return done > 0


_GREEK_PLURAL_ENDS = ('\u03bf\u03c5\u03c2', '\u03bf\u03b9\u03c2', '\u03b5\u03b9\u03c2', '\u03b1\u03b9\u03c2', '\u03c9\u03bd',
                      '\u03bf\u03b9', '\u03b1\u03b9', '\u03b1\u03c2', '\u03b5\u03c2')      # ους οις εις αις ων οι αι ας ες


def _greek_ethnic_stem(form):
    """The stem, in Greek letters, of a Greek plural or genitive plural (Ἀγριοφάγοι, Ἀγριοφάγων, Ἀγριοφάγους:
    αγριοφαγ), else ''. The omega keeps ων apart from the singular -ον."""
    t = ei.fold(prep(form)).replace('\u03c2', '\u03c3')
    for end in _GREEK_PLURAL_ENDS:
        e = end.replace('\u03c2', '\u03c3')
        if t.endswith(e) and len(t) - len(e) >= 5:
            return t[:-len(e)]
    return ''


def own_greek_labels(db, eid):
    """The Greek display labels of the entry (and of what it is merged into) that agree with a Latin heading of the
    entry in their first five letters once written in Latin letters (Ἀγριοφάγων with Agriofaguitai, Φαρίτιδος with
    Pharitae). A label that does not (Ἑκαταῖος, the commonest Greek spelling filed under Echecrates) is only the
    commonest spelling of the wrong group and is not a heading."""
    out = set()
    for e in {eid, merged_target(db, eid)}:
        r = db.execute('select display_label_grc from entity_labels where eid = ?', (e,)).fetchone()
        if r and r[0] and _is_greek(prep(r[0])):
            out.add(prep(r[0]))
    latin = {_vkey(mb._norm(h))[:5] for h in headings(db, eid) if not _is_greek(h) and mb._norm(h)}
    return {g for g in out if _vkey(mb._norm(g))[:5] in latin}


def is_own_greek(form, labels):
    """True when the spelling is the entry's own Greek label after the fold, or a Greek plural or genitive plural
    of the same ethnic stem as a plural label (Ἀγριοφάγοι, Ἀγριοφάγους for Ἀγριοφάγων)."""
    f = prep(form)
    if not _is_greek(f):
        return False
    fold = ei.fold(f)
    stem = _greek_ethnic_stem(f)
    return any(fold == ei.fold(g) or (stem and stem == _greek_ethnic_stem(g)) for g in labels)


def layer1(db, eid, pairs, lines=None):
    """pairs: {spelling: rows} of one entity. Returns (accepted, candidates) as sets of spellings. `lines` (a Lines)
    lets a spelling that is the front of a word broken across a line stay with its entry."""
    fam0 = Family(headings(db, eid))
    fam = Family(headings(db, eid))
    grc = own_greek_labels(db, eid)
    accepted = set()
    rest = set(pairs)
    changed = True
    while changed and rest:
        changed = False
        for f in sorted(rest):
            ok = belongs(f, fam)
            if ok and not belongs(f, fam0) and derivational_of(f, fam0):
                ok = False          # reached only through a spelling already accepted, and a derived name (Hecataeus)
            if not ok and _broken_completion(db, lines, eid, f, fam):
                ok = True
            if not ok and grc and is_own_greek(f, grc):
                ok = True
            if ok:
                accepted.add(f)
                rest.discard(f)
                fam.add(prep(f))
                changed = True
    return accepted, rest


def stem_of(form):
    return pr.group_stem(prep(form))


def audit(db, lines=None, only=None):
    """Layer 1 over every entity, or over the entity ids (entity_id strings) in `only` when it is given. Returns {'summary': counts per source, 'groups': [[eid, stem, {spelling: rows},
    rows]]} for the candidate groups."""
    src = {eid: (eid_s, s, t) for eid, eid_s, s, t in db.execute('select eid, entity_id, source, type from entities')}
    forms = {}
    for eid, form, n in db.execute('select eid, form, count(*) from mention_rows group by eid, form'):
        forms.setdefault(eid, {})[form] = n
    summ = {}
    groups = []
    for eid, pairs in forms.items():
        entity_id, source, _t = src[eid]
        if protected(entity_id) or (only is not None and entity_id not in only):
            continue
        s = summ.setdefault(source, {'entities': 0, 'entities_with_candidates': 0, 'spellings': 0,
                                     'candidate_spellings': 0, 'rows': 0, 'candidate_rows': 0, 'groups': 0})
        acc, rest = layer1(db, eid, pairs, lines)
        s['entities'] += 1
        s['spellings'] += len(pairs)
        s['rows'] += sum(pairs.values())
        if rest:
            s['entities_with_candidates'] += 1
        s['candidate_spellings'] += len(rest)
        s['candidate_rows'] += sum(pairs[f] for f in rest)
        by = {}
        for f in sorted(rest):
            by.setdefault(stem_of(f), []).append(f)
        s['groups'] += len(by)
        for st, fs in by.items():
            groups.append([eid, st, {f: pairs[f] for f in sorted(fs)}, sum(pairs[f] for f in fs)])
    summ['all'] = {k: sum(v[k] for v in summ.values()) for k in next(iter(summ.values()))}
    return {'summary': summ, 'groups': groups}


# ---------------------------------------------------------------- layer 2, the model

PROMPT_VERSION = 'v5'
SYSTEM = (
    'You check the work of a program that sorts the spellings of ancient proper names into entries of a '
    'reference index (People & Places). An entry has a heading, such as Marcus, and a short description. The '
    'program put a group of spellings under that entry, and many groups belong to a different name that begins '
    'with similar letters. You see the heading, the description, the group of spellings with the number of lines '
    'for each, and two lines of text where the group occurs, the spelling marked between the signs \u27e6 \u27e7. '
    'Answer SAME only when you can say which regular case form, spelling, script or language variant of the '
    'heading\'s own name the group is: a case form (Hectora for Hector), a transliteration (Greek letters or '
    'Latin letters for the same name), or the name of the same person, people, place or god in Greek, Latin '
    'or English (Venerem and \u1f08\u03c6\u03c1\u03bf\u03b4\u03af\u03c4\u03b7 for Venus). Answer DIFFERENT '
    'when the group is another person, place, god or people, or a different name whose letters merely look '
    'alike (Marcellus is not Marcus, Antiochia is not Antiochus). Letters inside the stem that differ from the '
    'heading make a different name, and so does a different referent in the lines (the famous king or city of '
    'another name). Do not explain a difference by a scribal error or a dialect form unless the lines show it. A '
    'place and its inhabitants are different names, and so are a person and a people or family of that name, '
    'unless the heading itself names both. Answer UNCLEAR only when the lines do not allow a decision. Reply in '
    'two lines. Line one: one sentence that gives the nominative of the group\'s name exactly as the spellings '
    'show it, compares it letter by letter with the heading, and says who the lines mean. A group whose own name '
    'differs from the heading in any letter of the stem is DIFFERENT, however the two are related in history '
    '(Marcus Aurelius and Marcus Antonius, Hannibal and Hasdrubal). Do not accept a variant spelling that you '
    'cannot see in the lines. Line two: exactly ANSWER: SAME or ANSWER: DIFFERENT or ANSWER: UNCLEAR.')


# Second pass (2026-10-22). The first pass was strict and called some spelling variants DIFFERENT (Caipha under
# Caiaphas, Samuhel under Samuel). The second pass sees only the groups the first called DIFFERENT, with the
# entry's labels and its most frequent spellings, and is told what counts as the same name.
PROMPT_VERSION2 = 'p2v7'
THINK2 = False
MAX_TOKENS2 = 600
SYSTEM2 = (
    'You check the work of a program that sorts the spellings of ancient proper names into entries of a '
    'reference index (People & Places). An entry has a heading, display labels, a short description and its most '
    'frequent spellings. An earlier check judged that a group of spellings under the entry belongs to another '
    'name. Check it again. You see the entry, the group of spellings with the number of lines for each, and two '
    'lines of text where the group occurs, the spelling marked between the signs \u27e6 \u27e7.\n'
    'Answer SAME when the group is a different spelling, case form, abbreviation, Latin or Greek '
    'transliteration, or scribal or OCR slip of the SAME person, people, place or god that the entry names. '
    'Examples of SAME: Caipha for Caiaphas, Samuhel for Samuel, Gedeona for Gideon, \u039a\u03c5\u03b8\u03b7\u03c1\u03af\u03b1 for Cythera, '
    '\u03a6\u03bf\u03af\u03bd\u03b9\u03c3\u03c3\u03b1\u03b9 for Phoenicians. Answer DIFFERENT when the group is another '
    'person, people, place or god, or a different word whose letters merely resemble the heading, even when '
    'the two are related. Examples of DIFFERENT: Maximin for Maximianus, \u1f18\u03c0\u03b9\u03ba\u03bf\u03cd\u03c1\u03bf\u03c5 '
    'for Epicureans, \u03a6\u03bf\u03c5\u03bb\u03b2\u03af\u03b1 for Fulvius. Decide by the group\'s own name, the nominative the spellings '
    'show. Compare it letter by letter with the heading and the entry\'s frequent spellings. The group is SAME '
    'only when it differs from them by ordinary variation of spelling and ending: ae and e, y and i, c and k, '
    'ph and f, th and t, a dropped or added h, ii and i, Greek letters for Latin letters, a Latin or Greek '
    'case ending, an English form. It is DIFFERENT when a consonant or a syllable of the stem differs (Maximin '
    'and Maximianus, Hermippus and Herippus, Pherecrates and Pherecydes, Hibernia and Hiberum), when it is a '
    'different word of the same family (Fulvia and Fulvius, a woman and a man), or when it is a person, school, '
    'family, people or place only connected with the entry (the Epicureans and Epicurus). Do not accept a '
    'group because the lines concern the person the heading names. Answer UNCLEAR only when the lines do not '
    'allow a decision. Reply in three lines. Line one: GROUP: the nominative of the group\'s most '
    'frequent spelling, taken from the line "Group in Latin letters" and never replaced by the heading. Line two: HEADING: the heading as written, then the '
    'stem letters of each side and whether they differ by more than the ordinary variation listed, with the '
    'differing letters named (for example: Maximin / Maximianus, differ: -in against -ian). Line three: exactly '
    'ANSWER: SAME or ANSWER: DIFFERENT or ANSWER: UNCLEAR.')


# Third version (p3v1): the second question for ONE spelling (the project lead's option B, 2026-10-22), because
# a group mixes names (Φουλβία with Φούλβιος) and a verdict on the group follows its commonest spelling.
PROMPT_VERSION3 = 'p3v1'
SYSTEM3 = (
    'You check the work of a program that sorts the spellings of ancient proper names into entries of a '
    'reference index (People & Places). An entry has a heading, display labels, a short description and its most '
    'frequent spellings. An earlier check judged that one spelling under the entry belongs to another '
    'name. Check it again. You see the entry, the spelling with the number of lines it occurs in, and two '
    'lines of text where it occurs, the spelling marked between the signs \u27e6 \u27e7.\n'
    'Answer SAME when the spelling is a different spelling, case form, abbreviation, Latin or Greek '
    'transliteration, or scribal or OCR slip of the SAME person, people, place or god that the entry names. '
    'Examples of SAME: Caipha for Caiaphas, Samuhel for Samuel, Gedeona for Gideon, \u039a\u03c5\u03b8\u03b7\u03c1\u03af\u03b1 for Cythera, '
    '\u03a6\u03bf\u03af\u03bd\u03b9\u03c3\u03c3\u03b1\u03b9 for Phoenicians. Answer DIFFERENT when the spelling is another '
    'person, people, place or god, or a different word whose letters merely resemble the heading, even when '
    'the two are related. Examples of DIFFERENT: Maximin for Maximianus, \u1f18\u03c0\u03b9\u03ba\u03bf\u03cd\u03c1\u03bf\u03c5 '
    'for Epicureans, \u03a6\u03bf\u03c5\u03bb\u03b2\u03af\u03b1 for Fulvius. Decide by the spelling\'s own name, the nominative it '
    'shows. Compare it letter by letter with the heading and the entry\'s frequent spellings. The spelling is SAME '
    'only when it differs from them by ordinary variation of spelling and ending: ae and e, y and i, c and k, '
    'ph and f, th and t, a dropped or added h, ii and i, Greek letters for Latin letters, a Latin or Greek '
    'case ending, an English form. It is DIFFERENT when a consonant or a syllable of the stem differs (Maximin '
    'and Maximianus, Hermippus and Herippus, Pherecrates and Pherecydes, Hibernia and Hiberum), when it is a '
    'different word of the same family (Fulvia and Fulvius, a woman and a man), or when it is a person, school, '
    'family, people or place only connected with the entry (the Epicureans and Epicurus). Do not accept the '
    'spelling because the lines concern the person the heading names. Answer UNCLEAR only when the lines do not '
    'allow a decision. Reply in three lines. Line one: SPELLING: the nominative of the spelling\'s name, '
    'written in Latin letters. Line two: HEADING: the entry\'s name in Latin letters, then the '
    'stem letters of each side and whether they differ by more than the ordinary variation listed, with the '
    'differing letters named (for example: Maximin / Maximianus, differ: -in against -ian). Line three: exactly '
    'ANSWER: SAME or ANSWER: DIFFERENT or ANSWER: UNCLEAR.')


def question3(heading, labels, top, description, form, n, lines):
    out = [f'Heading: {heading}']
    if labels:
        out.append('Display labels: ' + ', '.join(labels))
    if description:
        out.append(f'Description: {description}')
    out.append('Most frequent spellings of the entry: ' + ', '.join(top))
    out.append(f'Spelling: {form} ({n} lines)')
    for i, ln in enumerate(lines, 1):
        out.append(f'Line {i}: {ln[:400]}')
    return '\n'.join(out)


# Fourth version (p4v1): the third question plus a letter comparison computed in code (the model misread
# Ἑρμίππου as Herippus and wrote "identical stems"; the project lead, 2026-10-22).
PROMPT_VERSION4 = 'p4v8'
_VARIANTS = (('ae', 'e'), ('ph', 'f'), ('th', 't'), ('kh', 'k'), ('ch', 'k'), ('c', 'k'), ('y', 'i'), ('ii', 'i'),
             ('ei', 'i'), ('h', ''))


def _vkey(t):
    for a, b in _VARIANTS:
        t = t.replace(a, b)
    return t


def _prep_pair(form, heads):
    """The spelling without a Latin enclitic (Romanoque is Romano), and the headings without a parenthesis
    (Mycale (mountain)) and split at a slash (Ares/Mars), the way the letter check reads them."""
    base, _enc = ex.without_enclitic(form)
    f = prep(form)
    if base:
        f = base
    hs = set()
    for h in heads:
        h = re.sub(r'\s*\([^)]*\)', '', h).strip()
        for part in h.split('/'):
            if ei.fold(part):
                hs.add(part.strip())
    return f, hs


def _skeleton(stem):
    """The consonants of a stem, v and w written b, a doubled consonant once."""
    import re as _re
    t = _re.sub('[aeiouy]', '', stem.replace('v', 'b').replace('w', 'b'))
    return _re.sub(r'(.)\1+', r'\1', t)


def _sk_same(a, b, head='', form=''):
    """Two consonant skeletons agree when equal or when one is the other plus a final s (the nominative
    ending the stem rule did not take off: Caipha and Caiaphas) or, for a heading in -on, a final n (Gideon and
    Gedeona)."""
    if a == b:
        return True
    if a and b and a[-1] in 'sm' and b[-1] in 'sm' and a[:-1] == b[:-1]:
        return True          # nominative -s against accusative -m (Caiaphas, Caipham)
    a, b = sorted((a, b), key=len)
    if not (len(b) == len(a) + 1 and b.startswith(a)):
        return False
    greek_acc = _is_greek(form) and ei.translit(ei.fold(form))[-2:-1] in tuple('aeiou') and b[-1] == 'n'
    latin_acc = b[-1] == 'm' and not _is_greek(form) and ei.translit(ei.fold(form)).endswith('m')
    nasal = b[-1] in 'mn' and any(ei.translit(ei.fold(w))[-2:] in ('on', 'om', 'an', 'am', 'en', 'em') for w in (form, head) if w)
    return b[-1] == 's' or greek_acc or latin_acc or nasal or (b[-1] == 'n' and ei.translit(ei.fold(head)).endswith('on'))


def letter_compare(form, heads, limit=3):
    """Lines that compare the spelling with each of the entry's headings, computed, not judged: both written in
    Latin letters by the fold and transliteration the index uses, the case ending taken off, the ordinary
    variants (ae/e, y/i, c/k, ph/f, th/t, h) merged, then the letters only one side has and a similarity ratio.
    The `limit` closest headings are shown."""
    import difflib
    form0 = form
    form, heads = _prep_pair(form, heads)
    reading = ei.translit(ei.fold(form))
    sstem = _vkey(mb.case_family(form)[0])
    rows = []
    seen = set()
    for h in sorted(heads):
        hr = ei.translit(ei.fold(h))
        if not hr or hr in seen:
            continue
        seen.add(hr)
        hstem = _vkey(mb.case_family(h)[0])
        sm = difflib.SequenceMatcher(None, sstem, hstem)
        only_s, only_h = [], []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != 'equal':
                if sstem[i1:i2]:
                    only_s.append(f'-{sstem[i1:i2]}- (after {sstem[:i1][-2:] or "the start"})')
                if hstem[j1:j2]:
                    only_h.append(f'-{hstem[j1:j2]}- (after {hstem[:j1][-2:] or "the start"})')
        rows.append((sm.ratio(), h, hr, hstem, only_s, only_h, _skeleton(hstem)))
    rows.sort(key=lambda r: -r[0])
    out = [f'Letter check (computed by program, breathings and accents left out): the spelling {form0} reads {reading}, '
           f'its stem is {sstem}.']
    sk = _skeleton(sstem)
    for ratio, h, hr, hstem, only_s, only_h, hsk in rows[:limit]:
        diff = ('the stems are IDENTICAL after the ordinary variants' if not only_s and not only_h else
                'the stems DIFFER, only in the spelling: ' + (', '.join(only_s) or 'nothing') + '; only in the heading: ' + (', '.join(only_h) or 'nothing'))
        out.append(f'Against {h}: it reads {hr}, stem {hstem}, similarity {ratio:.2f}, {diff}. '
                   f'Consonants of the stems: {sk or "none"} against {hsk or "none"}, '
                   f'{"IDENTICAL, only vowels or h differ" if _sk_same(sk, hsk, h, form) else "they DIFFER"}.')
    return '\n'.join(out)


SYSTEM4 = SYSTEM3.split(' Decide by the spelling')[0] + (
    ' Decide by the spelling\'s own name. A program has compared its letters with the headings of the entry '
    'and printed the result under "Letter check". Trust the letter check for what the letters are, and do not '
    'replace the spelling by a heading. When the check says the consonants of the stems DIFFER from those of every '
    'heading, the answer is DIFFERENT (a consonant or syllable that one side lacks: Hermippus and Herippus). One '
    'exception: when a heading is the Latin or English name of the same people, place or god that the spelling '
    'writes in Greek (Phoenicians for \u03a6\u03bf\u03af\u03bd\u03b9\u03c3\u03c3\u03b1\u03b9, Venus for \u1f08\u03c6\u03c1\u03bf\u03b4\u03af\u03c4\u03b7), the answer is SAME. '
    'When the consonants are IDENTICAL, only vowels or h differ, which is ordinary variation (Caipha and '
    'Caiaphas, Gedeona and Gideon), and the answer is SAME unless the spelling is another name of the same '
    'family (Maximin and Maximianus, Fulvia and Fulvius, Demetrius and Demeter), a person, school, family, '
    'people or place only connected with the entry (the Epicureans and Epicurus), or the lines show another '
    'person, people, place or god. Answer UNCLEAR only when the lines do not allow a decision. Reply in three '
    'lines. Line one: SPELLING: the nominative of the spelling\'s name in Latin letters, from the letter check. '
    'Line two: CONSONANTS: identical or differ, and the letters that differ. Line three: EXCEPTION: yes only when '
    'a heading is the Latin or English name of the same people, place or god written in Greek, else no. Line '
    'four: exactly ANSWER: SAME or ANSWER: DIFFERENT or ANSWER: UNCLEAR.')


def consonants_differ(form, heads):
    """True when the consonant skeleton of the spelling's stem differs from that of every heading's stem (the
    same test the letter check prints), so that no heading is the spelling with only vowels or h changed."""
    form, heads = _prep_pair(form, heads)
    sk = _skeleton(_vkey(mb.case_family(form)[0]))
    hs = [h for h in heads if ei.fold(h)]
    return bool(hs) and not any(_sk_same(_skeleton(_vkey(mb.case_family(h)[0])), sk, h, form) for h in hs)


def is_variant(form, heads):
    """True when the spelling is a spelling variant of a heading (third pass 2026-10-24): the consonant skeletons of
    their stems agree (doubled consonants, v and b, e and a inserted vowels, a final s, m or n do not count) and
    neither goes on with a derivational suffix the other lacks (Hecataeus and Hecate, Maximin and Maximianus,
    Graeculus and Graeci are other names)."""
    form, hs = _prep_pair(form, heads)
    for h in hs:
        if word_suffix(form) != word_suffix(h):
            continue
        if not consonants_differ(form, {h}):
            return True
    return False


def final_answer4(reply, form, heads):
    """The answer stored for the p4 question. The model's own answer, except that when the computed consonants
    differ from every heading and the model does not claim the exception (a name in another language), the answer
    is DIFFERENT. The model contradicted its own consonant line (Hibernia, 'extra n', SAME) without this rule."""
    ans, _ = parse_answer(reply)
    if ans is None:
        return None
    exc = re.findall(r'EXCEPTION:\s*\**\s*(yes|no)', reply or '', re.I)
    if ans == 'SAME' and consonants_differ(form, heads) and not (exc and exc[-1].lower() == 'yes'):
        return 'DIFFERENT'
    return ans


def question4(heading, labels, top, description, form, n, lines, heads):
    return question3(heading, labels, top, description, form, n, lines) + '\n' + letter_compare(form, heads)


def open_cache2(path):
    c = sqlite3.connect(path)
    c.execute('create table if not exists answers2 (entity_id text, stem text, version text, answer text, '
              'reply text, forms text, primary key (entity_id, stem, version))')
    c.commit()
    return c


def entity_card2(db, eid, n_top=5):
    """(heading, labels, top spellings) for the second question: the heading, the display labels, and the
    entry's n_top most frequent spellings (excluding none)."""
    t = merged_target(db, eid)
    heading, _d = entity_card(db, eid)
    r = db.execute('select display_label, display_label_la, display_label_grc from entity_labels where eid = ?',
                   (t,)).fetchone()
    labels = []
    for x in (r or ()):
        if x and x not in labels and x != heading:
            labels.append(x)
    top = [f for f, _n in db.execute('select form, count(*) c from mention_rows where eid = ? group by form '
                                     'order by c desc, form limit ?', (eid, n_top))]
    return heading, labels, top


def question2(heading, labels, top, description, forms, lines):
    out = [f'Heading: {heading}']
    if labels:
        out.append('Display labels: ' + ', '.join(labels))
    if description:
        out.append(f'Description: {description}')
    out.append('Most frequent spellings of the entry: ' + ', '.join(top))
    ranked = sorted(forms.items(), key=lambda x: -x[1])
    out.append('Group of spellings: ' + ', '.join(f'{f} ({n})' for f, n in ranked[:12]))
    out.append('Group in Latin letters: ' + ', '.join(ei.translit(ei.fold(f)) for f, _n in ranked[:6]))
    for i, ln in enumerate(lines, 1):
        out.append(f'Line {i}: {ln[:400]}')
    return '\n'.join(out)


def mark(text, form):
    """`text` with the first occurrence of the spelling between the signs, or the text unchanged."""
    i = text.find(form)
    if i < 0:
        i = text.lower().find(form.lower())
    if i < 0:
        return text
    return text[:i] + '⟦' + text[i:i + len(form)] + '⟧' + text[i + len(form):]


def question(heading, description, forms, lines):
    """The user message. forms: {spelling: rows}, lines: [text with the spelling already marked]."""
    out = [f'Heading: {heading}']
    if description:
        out.append(f'Description: {description}')
    out.append('Group of spellings: ' + ', '.join(f'{f} ({n})' for f, n in sorted(forms.items(), key=lambda x: -x[1])[:12]))
    for i, ln in enumerate(lines, 1):
        out.append(f'Line {i}: {ln[:400]}')
    return '\n'.join(out)


def parse_answer(text):
    """('SAME'|'DIFFERENT'|'UNCLEAR', reasons) from the reply, or (None, text) when it has no answer line."""
    m = re.findall(r'ANSWER:\s*\**\s*(SAME|DIFFERENT|UNCLEAR)', text or '', re.I)
    if not m:
        return None, text or ''
    return m[-1].upper(), (text or '').strip()


def open_cache(path):
    c = sqlite3.connect(path)
    c.execute('create table if not exists answers (entity_id text, stem text, version text, answer text, '
              'reply text, forms text, primary key (entity_id, stem, version))')
    c.commit()
    return c


def merged_target(db, eid):
    r = db.execute('select list_eid from entity_merges where eid = ?', (eid,)).fetchone()
    return r[0] if r else eid


def entity_card(db, eid):
    """(heading, description) the question shows. An entry merged into a list entity shows the list entity's."""
    t = merged_target(db, eid)
    label = db.execute('select label from entities where eid = ?', (t,)).fetchone()[0]
    r = db.execute('select display_label, description from entity_labels where eid = ?', (t,)).fetchone()
    heading = (r[0] if r and r[0] else label) or label
    return heading, (r[1] if r and r[1] else '')


class Lines:
    """The text lines of the corpus (window_texts.db) for the example lines of a group."""

    def __init__(self, path):
        self.db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)

    def line(self, work, ref, form):
        if ref:
            r = self.db.execute('select text from lines where work = ? and ref = ? limit 1', (work, ref)).fetchone()
            if r and r[0] and (form in r[0] or form.lower() in r[0].lower()):
                return r[0].strip()
        return None


def example_lines(db, lines, eid, forms, n=2, window_fallback=True):
    """Up to n marked example lines, from different works where possible, for mention rows of eid whose
    spelling is in `forms`."""
    ph = ','.join('?' * len(forms))
    rows = db.execute(f'select m.form, m.line_ref, w.work, w.window_id from mention_rows m join windows w using(wid) '  # nosec B608 - ph is only ? marks, the values are bound
                      f'where m.eid = ? and m.form in ({ph}) limit 60', (eid, *forms)).fetchall()
    seen, out = set(), []
    rows.sort(key=lambda r: (r[2] in seen, r[3]))
    used = set()
    for form, ref, work, wid in rows:
        if work in used and len(used) < n:
            continue
        t = lines.line(work, ref, form)
        if t is None and window_fallback:
            r = lines.db.execute('select text from window_texts where id = ?', (wid,)).fetchone()
            if r and r[0]:
                for ln in r[0].split('\n'):
                    if form in ln or form.lower() in ln.lower():
                        t = ln.strip()
                        break
        if t:
            out.append(f'({work}) ' + mark(t, form))
            used.add(work)
        if len(out) >= n:
            break
    return out


MODEL = 'Qwen/Qwen3.8-27B-FP8'
MAX_TOKENS = 400


def ask(url, key, user, stats=None, system=SYSTEM, model=MODEL, tries=6, think=False, max_tokens=None):
    """One chat completion from the campus gateway (free), thinking off. Returns the reply or None. A 429 or an
    error waits and tries again."""
    import json
    import time
    import urllib.error
    import urllib.request
    body = json.dumps({'model': model, 'temperature': 0, 'max_tokens': max_tokens or MAX_TOKENS,
                       'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                       'chat_template_kwargs': {'enable_thinking': bool(think)}}).encode()
    if not str(url).startswith(('https://', 'http://')):
        raise ValueError('the gateway address must be an http or https URL')
    req = urllib.request.Request(url + '/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    for _ in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:  # nosec B310 - gateway address from the configuration, http(s) only
                d = json.loads(r.read())
            if stats is not None:
                stats['requests'] = stats.get('requests', 0) + 1
            return d['choices'][0]['message']['content'] or ''
        except urllib.error.HTTPError as e:
            if stats is not None:
                stats['errors'] = stats.get('errors', 0) + 1
            if e.code in (402,):
                raise RuntimeError('gateway quota (HTTP 402)')
            time.sleep(30 if e.code == 429 else 5)
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError):
            if stats is not None:
                stats['errors'] = stats.get('errors', 0) + 1
            time.sleep(5)
    return None


# ---------------------------------------------------------------- apply

class Targets:
    """Every entity's headings indexed by case stem, to find the entity a wrong spelling is a case form of."""

    def __init__(self, db):
        self.db = db
        self.ids = dict(db.execute('select eid, entity_id from entities'))
        self.source = dict(db.execute('select eid, source from entities'))
        self.by_stem = {}
        self.heads = {}
        for eid, entity_id in self.ids.items():
            if protected(entity_id):
                continue
            hs = _own_headings(db, eid)
            hs = {h for h in hs if ei.fold(h)}
            self.heads[eid] = hs
            for h in sorted(hs):
                self.by_stem.setdefault(mb.case_family(h)[0], set()).add(eid)

    def of(self, form, exclude):
        """The one entity (an eid) whose headings the spelling is a case form of, None for none or several.
        exclude: eids that do not count (the entry it comes from and what that is merged into)."""
        form = prep(form)
        t = mb._norm(form)
        base, _enc = ex.without_enclitic(form)
        cand = set()
        for s in (t, mb._norm(base) if base else ''):
            for n in range(3, len(s) + 1):
                cand |= self.by_stem.get(s[:n], set())
        hits = set()
        for eid in cand - set(exclude):
            if belongs(form, Family(self.heads[eid])):
                hits.add(eid)
        owners = {merged_target(self.db, e) for e in hits}
        if len(owners) != 1:
            return None
        return sorted(hits, key=lambda e: (self.source[e] != 'names', e))[0]


def _move_all(db, src, dst, folds):
    """Move every mention row and document row of the spellings with these folds from src to the new, empty
    entity dst. Unlike pr._move_rows nothing is dropped as a duplicate, because dst holds no rows yet."""
    moved = 0
    for rowid, form in db.execute('select rowid, form from mention_rows where eid = ?', (src,)).fetchall():
        if ei.fold(form) in folds:
            db.execute('update mention_rows set eid = ? where rowid = ?', (dst, rowid))
            moved += 1
    for rowid, form in db.execute('select rowid, form from document_mentions where eid = ?', (src,)).fetchall():
        if ei.fold(form) in folds:
            db.execute('update document_mentions set eid = ? where rowid = ?', (dst, rowid))
    return moved, 0


def carve(db, host, forms, serial):
    """Make a corpus-name entity of source 'names' from the spellings `forms` of entity `host`: its mention rows
    and document rows move, and so do the host's listed spellings that are those forms. Returns (eid, entity_id,
    counts)."""
    counts = {f: n for f, n in db.execute('select form, count(*) from mention_rows where eid = ? group by form', (host,))
              if f in forms}
    label = max(counts, key=lambda f: (counts[f], f)) if counts else sorted(forms)[0]
    key = ei.names_key(label) or db.execute('select name_key from entities where eid = ?', (host,)).fetchone()[0]
    n = serial.get(key, 0)
    while True:
        n += 1
        entity_id = f'nm:{key}:r{n}'
        if not db.execute('select 1 from entities where entity_id = ?', (entity_id,)).fetchone():
            break
    serial[key] = n
    eid = db.execute('select max(eid) from entities').fetchone()[0] + 1
    db.execute("insert into entities(eid, entity_id, type, label, source, name_key, distinctive, n_windows) "
               "values (?, ?, 'name', ?, 'names', ?, 0, 0)", (eid, entity_id, label, key))
    folds = {ei.fold(f) for f in forms}
    moved, dropped = _move_all(db, host, eid, folds)
    disp, la, grc = pr.display_labels(counts)
    db.execute('insert or replace into entity_labels values (?,?,?,?,NULL)', (eid, label, la, grc))
    seen = set()
    for rowid, f, lang, role, source in db.execute('select rowid, form, language, role, source from variants '
                                                  'where eid = ?', (host,)).fetchall():
        if ei.fold(f) in folds:
            db.execute('delete from variants where rowid = ?', (rowid,))
    for f in sorted(forms):
        ff = ei.fold(f)
        if ff and ff not in seen:
            seen.add(ff)
            db.execute('insert into variants values (?,?,?,?,?)', (eid, ff, '', 'form', 'names'))
    pr._refresh_windows(db, [host, eid])
    _move_search_names(db, host, eid, label)
    return eid, entity_id, {'moved': moved, 'dropped': dropped}


def _followers(db, host, new, label):
    """After a group was carved from `host` into the entity `new` (heading `label`), the host's other spellings that
    are case forms of that heading and not of the host's own headings go with it (Maximinum, Maximini, Maximine
    with Maximinus, split from Maximianus). Returns the number of rows moved."""
    fam_new = Family({prep(label)})
    fam_host = Family(headings(db, host))
    forms = [f for (f,) in db.execute('select distinct form from mention_rows where eid = ?', (host,))]
    take = {f for f in forms if belongs(f, fam_new) and not belongs(f, fam_host)}
    if not take:
        return 0
    folds = {ei.fold(f) for f in take}
    moved, _d = _move_all(db, host, new, folds)
    for rowid, f in db.execute('select rowid, form from variants where eid = ?', (host,)).fetchall():
        if ei.fold(f) in folds:
            db.execute('delete from variants where rowid = ?', (rowid,))
    for ff in sorted(folds):
        if ff:
            db.execute('insert into variants values (?,?,?,?,?)', (new, ff, '', 'form', 'names'))
    pr._refresh_windows(db, [host, new])
    return moved


def _move_exact_names(db, host, new):
    """The host's model search names that are, once folded, one of the spellings now filed under `new` and no
    heading of the host go to `new` (Maximinus, listed under Maximianus, goes with the carved Maximinus)."""
    own = {ei.fold(f) for (f,) in db.execute('select form from variants where eid = ?', (new,))}
    keep = {ei.fold(h) for h in headings(db, host)}
    for rowid, name in db.execute("select rowid, name from search_names where eid = ? and source = 'model'", (host,)).fetchall():
        f = ei.fold(name)
        if f in own and f not in keep:
            db.execute('update search_names set eid = ? where rowid = ?', (new, rowid))


def _letters(s):
    return mb._norm(s).replace('h', '')


def _move_search_names(db, host, new, label):
    """The model's search names of the host that name the carved spelling (Hecataeus, for the spelling
    \u1f1d\u03ba\u03b1\u03c4\u03b1\u1fd6\u03bf\u03c2 carved out of Echecrates) go to the new entity: they share the first five letters of the
    carved label, with the h left out, and not the first four of a heading the host keeps."""
    lab = _letters(label)
    if len(lab) < 5:
        return
    keep = [_letters(h) for h in headings(db, host)]
    for rowid, name in db.execute("select rowid, name from search_names where eid = ? and source = 'model'", (host,)).fetchall():
        n = _letters(name)
        if n[:5] == lab[:5] and not any(k[:4] == n[:4] for k in keep if k):
            db.execute('update search_names set eid = ? where rowid = ?', (new, rowid))


def apply_differences(db, differences, log=print, cap=300):
    """differences: [(entity_id, stem, {spelling: rows})] the model judged DIFFERENT. Moves a spelling that is a
    case form of the heading of exactly one other entity there (mb.apply_partial), carves the rest of each
    group into a new corpus name. Returns the counts."""
    tg = Targets(db)
    eid_of = {v: k for k, v in tg.ids.items()}
    serial = {}
    rep = {'groups': 0, 'moved_groups': 0, 'carved_groups': 0, 'rows_moved': 0, 'rows_carved': 0,
           'rows_dropped': 0, 'spellings_moved': 0, 'carved_entities': 0, 'skipped_protected': 0, 'moves': [],
           'carves': []}
    for entity_id, stem, forms in differences:
        host = eid_of.get(entity_id)
        if host is None or protected(entity_id):
            rep['skipped_protected'] += 1
            continue
        rep['groups'] += 1
        exclude = {host, merged_target(db, host)}
        by_dst, rest = {}, []
        for f in sorted(forms):
            dst = tg.of(f, exclude)
            if dst is None:
                rest.append(f)
            else:
                by_dst.setdefault(dst, []).append(f)
        for dst, fs in by_dst.items():
            r = mb.apply_partial(db, host, dst, fs)
            rep['moved_groups'] += 1
            rep['rows_moved'] += r['moved']
            rep['rows_dropped'] += r['dropped']
            rep['spellings_moved'] += len(fs)
            if cap is None or len(rep['moves']) < cap:
                rep['moves'].append([entity_id, tg.ids[dst], fs[:4], r['moved']])
        if rest:
            new, new_id, r = carve(db, host, set(rest), serial)
            label = db.execute('select label from entities where eid = ?', (new,)).fetchone()[0]
            r['moved'] += _followers(db, host, new, label)
            _move_exact_names(db, host, new)
            rep['carved_groups'] += 1
            rep['carved_entities'] += 1
            rep['rows_carved'] += r['moved']
            rep['rows_dropped'] += r['dropped']
            if cap is None or len(rep['carves']) < cap:
                rep['carves'].append([entity_id, new_id, rest[:4], r['moved']])
    return rep
