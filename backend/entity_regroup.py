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

from backend import entity_extras as ex
from backend import entity_index as ei
from backend import entity_mergeback as mb
from backend import entity_promote as pr

PROTECTED_IDS = ('nm:lauin:main', 'pl:393444')
PROTECTED_PREFIXES = ('pn:lauinia', 'nm:lauinia')
_GREEK = re.compile('[Ͱ-Ͽἀ-῿]')


def protected(entity_id):
    return entity_id in PROTECTED_IDS or str(entity_id).startswith(PROTECTED_PREFIXES)


def prep(s):
    """A spelling with the lunate sigma written as sigma (the fold keeps it apart)."""
    return str(s or '').replace('ϲ', 'σ').replace('Ϲ', 'Σ')


def _is_greek(s):
    return bool(_GREEK.search(s))


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
    return heads


_AS_FIRST = frozenset(mb._n('a', 'ae', 'am', 'an', 'ai', 'as', 'e', 'en'))
_AS_THIRD = frozenset(mb._n('a', 'os', 'i', 'em', 'es', 'ibus', 'um', 'on', 'is', 'u', 'ou', 'oi', 'ai', 'an', 'es'))


class Family:
    """The heading strings of one entity, indexed by case stem so that a spelling is tested only against the
    headings whose stem begins it."""

    def __init__(self, heads=()):
        self.by_stem = {}
        self.folded = set()
        self.stems_as = set()
        for h in heads:
            self.add(h)

    def add(self, h):
        stem = mb.case_family(h)[0]
        lst = self.by_stem.setdefault(stem, [])
        if h not in lst:
            lst.append(h)
        self.folded.add(mb._norm(h))
        n = mb._norm(h)
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


def layer1(db, eid, pairs):
    """pairs: {spelling: rows} of one entity. Returns (accepted, candidates) as sets of spellings."""
    fam = Family(headings(db, eid))
    accepted = set()
    rest = set(pairs)
    changed = True
    while changed and rest:
        changed = False
        for f in sorted(rest):
            if belongs(f, fam):
                accepted.add(f)
                rest.discard(f)
                fam.add(prep(f))
                changed = True
    return accepted, rest


def stem_of(form):
    return pr.group_stem(prep(form))


def audit(db):
    """Layer 1 over every entity. Returns {'summary': counts per source, 'groups': [[eid, stem, {spelling: rows},
    rows]]} for the candidate groups."""
    src = {eid: (eid_s, s, t) for eid, eid_s, s, t in db.execute('select eid, entity_id, source, type from entities')}
    forms = {}
    for eid, form, n in db.execute('select eid, form, count(*) from mention_rows group by eid, form'):
        forms.setdefault(eid, {})[form] = n
    summ = {}
    groups = []
    for eid, pairs in forms.items():
        entity_id, source, _t = src[eid]
        if protected(entity_id):
            continue
        s = summ.setdefault(source, {'entities': 0, 'entities_with_candidates': 0, 'spellings': 0,
                                     'candidate_spellings': 0, 'rows': 0, 'candidate_rows': 0, 'groups': 0})
        acc, rest = layer1(db, eid, pairs)
        s['entities'] += 1
        s['spellings'] += len(pairs)
        s['rows'] += sum(pairs.values())
        if rest:
            s['entities_with_candidates'] += 1
        s['candidate_spellings'] += len(rest)
        s['candidate_rows'] += sum(pairs[f] for f in rest)
        by = {}
        for f in rest:
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
    rows = db.execute(f'select m.form, m.line_ref, w.work, w.window_id from mention_rows m join windows w using(wid) '
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


def ask(url, key, user, stats=None, system=SYSTEM, model=MODEL, tries=6):
    """One chat completion from the campus gateway (free), thinking off. Returns the reply or None. A 429 or an
    error waits and tries again."""
    import json
    import time
    import urllib.error
    import urllib.request
    body = json.dumps({'model': model, 'temperature': 0, 'max_tokens': MAX_TOKENS,
                       'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                       'chat_template_kwargs': {'enable_thinking': False}}).encode()
    req = urllib.request.Request(url + '/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    for _ in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
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
            for h in hs:
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


def apply_differences(db, differences, log=print):
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
            if len(rep['moves']) < 300:
                rep['moves'].append([entity_id, tg.ids[dst], fs[:4], r['moved']])
        if rest:
            new, new_id, r = carve(db, host, set(rest), serial)
            rep['carved_groups'] += 1
            rep['carved_entities'] += 1
            rep['rows_carved'] += r['moved']
            rep['rows_dropped'] += r['dropped']
            if len(rep['carves']) < 300:
                rep['carves'].append([entity_id, new_id, rest[:4], r['moved']])
    return rep
