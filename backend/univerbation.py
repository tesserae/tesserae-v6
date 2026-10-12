"""Latin words that editors print either joined or apart (Line Search).

The lemma table gives a joined form its own lemma (quousque), while the same
words printed apart ("quo usque") lemmatise to qui and usque, so a search for
one spelling shared nothing with a line printing the other. This module holds
a short curated list of such words and works out, at the level of LEMMAS
(because the compounds inflect: rempublicam, reipublicae, iurisiurandi), how
a query and an indexed line can answer each other.

Only the query side of Line Search uses it. Nothing in the index, the lemma
cache or the lemma table changes.

Two directions:

  forward  the query has the parts ("quo usque"); a line holding the joined
           word (quousque) answers each part. `expand_parts`.
  reverse  the query has the joined word ("quousque"); a line holding the
           parts answers it, but only if the parts stand next to each other
           in the line in order, otherwise every line with qui and usque
           would match. `expand_joined` and `match_line`.

The lemmatiser is passed in (a function from a word to a set of folded
lemmas) so this module needs no import of the web application.
"""
import logging
import re

from backend.latin_orthography import fold_latin

logger = logging.getLogger(__name__)

UNIVERBATIONS_LA = {
    'quousque': ('quo', 'usque'), 'quamdiu': ('quam', 'diu'), 'quemadmodum': ('quem', 'ad', 'modum'),
    'quapropter': ('qua', 'propter'), 'quamobrem': ('quam', 'ob', 'rem'), 'quodsi': ('quod', 'si'),
    'siquidem': ('si', 'quidem'), 'etiamsi': ('etiam', 'si'), 'nihilominus': ('nihilo', 'minus'),
    'quandoquidem': ('quando', 'quidem'), 'quominus': ('quo', 'minus'), 'postquam': ('post', 'quam'),
    'antequam': ('ante', 'quam'), 'priusquam': ('prius', 'quam'), 'uerumtamen': ('uerum', 'tamen'),
    'respublica': ('res', 'publica'), 'iusiurandum': ('ius', 'iurandum'),
    'paterfamilias': ('pater', 'familias'), 'senatusconsultum': ('senatus', 'consultum'),
}

# The compounds that inflect in every part: a query of "rem publicam" is the
# parts of respublica by lemma. For the rest the parts are particles that do
# not inflect, and a query word must be the part itself ("qui usque" is not
# "quo usque", though both lemmatise to qui).
INFLECTING = frozenset({'respublica', 'iusiurandum', 'paterfamilias', 'senatusconsultum'})

# The joined surface forms of each inflecting compound, as editors print them
# (checked against the Latin index 2026-10-12). The lemma table gives some of
# these their joined lemma (rempublicam is respublica) and others only
# themselves (iurisiurandi, senatusconsulto), so the lemmas of every form
# listed here, and the forms themselves, count as the joined lemma.
INFLECTED_FORMS = {
    'respublica': ('respublica', 'reipublicae', 'rempublicam', 'republica', 'respublicae',
                   'rerumpublicarum', 'respublicas', 'rebuspublicis'),
    'iusiurandum': ('iusiurandum', 'iurisiurandi', 'iuriiurando', 'iureiurando', 'iuraiuranda',
                    'iurejurando', 'iusjurandum'),
    'paterfamilias': ('paterfamilias', 'patrisfamilias', 'patrifamilias', 'patremfamilias',
                      'patrefamilias', 'patresfamilias', 'patrumfamilias', 'patribusfamilias',
                      'patrisfamiliae', 'patrifamiliae', 'patremfamiliae', 'patrefamiliae'),
    'senatusconsultum': ('senatusconsultum', 'senatusconsulti', 'senatusconsulto',
                         'senatusconsulta', 'senatusconsultorum', 'senatusconsultis'),
}


def norm_token(token):
    """A word reduced the way the index folds it: lower case, no punctuation,
    u for v and i for j."""
    return fold_latin(re.sub(r'[^\w]', '', str(token or '').lower()))


class Entry:
    __slots__ = ('joined', 'parts', 'joined_lemmas', 'part_lemmas', 'inflecting', 'forms')

    def __init__(self, joined, parts, joined_lemmas, part_lemmas, forms=frozenset()):
        self.joined = joined
        self.forms = forms
        self.parts = parts
        self.joined_lemmas = joined_lemmas
        self.part_lemmas = part_lemmas
        self.inflecting = joined in INFLECTING


_TABLE = None
_DROPPED = []


def load_table(lemmatize):
    """The usable entries, computed once. `lemmatize(word)` returns a set of
    lemmas already folded for the index. An entry is dropped (and logged) when
    its joined form has no lemma, or when its joined lemma equals one of its
    part lemmas, which means the lemmatiser already splits it."""
    global _TABLE
    if _TABLE is not None:
        return _TABLE
    entries = {}
    dropped = []
    for joined, parts in UNIVERBATIONS_LA.items():
        forms = frozenset(fold_latin(f) for f in INFLECTED_FORMS.get(joined, ()))
        jl = frozenset(l for l in lemmatize(joined) if l)
        if jl:
            # every listed form: what the lemmatiser makes of it, and the form
            # itself, since the index holds some under their own spelling
            for f in INFLECTED_FORMS.get(joined, ()):
                jl = jl | frozenset(l for l in lemmatize(f) if l)
            jl = jl | forms
        pl = tuple(frozenset(l for l in lemmatize(p) if l) for p in parts)
        if not jl or any(not s for s in pl):
            dropped.append((joined, 'no lemma for the joined form or a part'))
            continue
        if any(jl & s for s in pl):
            dropped.append((joined, 'joined lemma equals a part lemma'))
            continue
        entries[joined] = Entry(joined, parts, jl, pl, forms)
    for joined, why in dropped:
        logger.info('[UNIVERBATION] dropped %s: %s', joined, why)
    _DROPPED[:] = dropped
    _TABLE = entries
    return entries


def dropped_entries():
    return list(_DROPPED)


def _token_lemmas(token, lemmatize):
    n = norm_token(token)
    return n, (frozenset(lemmatize(n)) | {n}) if n else frozenset()


def _part_matches(entry, k, token_norm, token_lemmas):
    if token_norm == fold_latin(entry.parts[k]):
        return True
    return entry.inflecting and bool(token_lemmas & entry.part_lemmas[k])


def expand_parts(query_tokens, lemmatize):
    """Forward direction. For each run of two or three adjacent query tokens
    that are the parts of an entry, {part lemma: {joined lemma}} (the part
    lemma is every lemma the typed part has). A line holding the joined word
    then counts as a hit on each part."""
    table = load_table(lemmatize)
    toks = [_token_lemmas(t, lemmatize) for t in query_tokens]
    out = {}
    for entry in table.values():
        n = len(entry.parts)
        for i in range(len(toks) - n + 1):
            if all(toks[i + k][0] and _part_matches(entry, k, *toks[i + k]) for k in range(n)):
                for k in range(n):
                    lemmas = (toks[i + k][1] & entry.part_lemmas[k]) or set(entry.part_lemmas[k])
                    for lem in lemmas:
                        out.setdefault(lem, set()).update(entry.joined_lemmas)
    return out


def expand_joined(query_tokens, lemmatize, stopwords=()):
    """Reverse direction. For each query token whose lemma is a joined lemma
    in the table, ({joined lemma: set of its part lemmas minus stopwords},
    {joined lemma: (tuple of part-lemma sets, tuple of part surface forms or
    None for a compound that inflects)}). The first is the fallback
    reading (a line holding a non-stopword part is a candidate for the
    joined word), the second is what `match_line` checks the candidate
    against, adjacent and in order."""
    table = load_table(lemmatize)
    fallbacks, sequences = {}, {}
    seen = set()
    for t in query_tokens:
        n, lemmas = _token_lemmas(t, lemmatize)
        if not n:
            continue
        for entry in table.values():
            if entry.joined in seen:
                continue
            if n == fold_latin(entry.joined) or n in entry.forms or (lemmas & entry.joined_lemmas):
                seen.add(entry.joined)
                parts = set()
                for s in entry.part_lemmas:
                    parts |= {l for l in s if l not in stopwords}
                for jl in entry.joined_lemmas:
                    fallbacks.setdefault(jl, set()).update(parts)
                    sequences[jl] = (entry.part_lemmas,
                                     None if entry.inflecting else tuple(fold_latin(p) for p in entry.parts))
    return fallbacks, sequences


def merge_fallbacks(*dicts):
    """Union of fallback dicts ({lemma: set}); None entries are skipped.
    Returns None when nothing is left."""
    out = {}
    for d in dicts:
        for k, v in (d or {}).items():
            out.setdefault(k, set()).update(v)
    return out or None


def joined_answers(forward):
    """Invert expand_parts: {joined lemma: set of part lemmas it answers}."""
    inv = {}
    for part, joined in (forward or {}).items():
        for j in joined:
            inv.setdefault(j, set()).add(part)
    return inv


def match_line(token_lemmas, tokens, query_lemmas, forward=None, sequences=None):
    """Which of the query's lemmas a line answers, counting joined words as
    the parts they stand for.

    token_lemmas  per token, an iterable of that token's lemmas
    tokens        the line's tokens, same length
    query_lemmas  the (filtered) query lemmas
    forward       expand_parts result
    sequences     expand_joined's second result

    Returns (matched_lemma_set, matched_words, matched_positions), words and
    positions in line order. A joined token that answers parts of the query
    is one word and one position. A run of part tokens that answers a joined
    query lemma is checked adjacent and in order, and every token of the run
    is a matched word."""
    answers = joined_answers(forward)
    matched = set()
    by_pos = {}
    lemma_sets = [set(l) for l in token_lemmas]
    # A joined token answers the parts the query typed. A part answered that
    # way is not marked again wherever the same word stands alone in the line:
    # a long prose sentence holding "quousque tandem" and a stray "usque"
    # three hundred words on would otherwise be judged "key words apart".
    answered = set()
    for i, lems in enumerate(lemma_sets):
        if i >= len(tokens):
            break
        hit = set()
        for j in lems:
            if j in answers:
                hit |= answers[j] & query_lemmas
        if hit:
            answered |= hit
            matched |= hit
            by_pos[i] = tokens[i]
    for i, lems in enumerate(lemma_sets):
        if i >= len(tokens):
            break
        hit = (lems & query_lemmas) - answered
        if hit:
            matched |= hit
            by_pos[i] = tokens[i]
    for joined_lemma, seq in (sequences or {}).items():
        if joined_lemma not in query_lemmas or joined_lemma in matched:
            continue
        part_lemmas, part_surfaces = seq
        n = len(part_lemmas)
        for i in range(len(token_lemmas) - n + 1):
            if i + n > len(tokens):
                break
            # By lemma, and for the particle compounds also by surface form
            # ("cuius usque" is qui + usque by lemma but is not quo usque).
            if all(set(token_lemmas[i + k]) & part_lemmas[k]
                   and (part_surfaces is None or norm_token(tokens[i + k]) == part_surfaces[k])
                   for k in range(n)):
                matched.add(joined_lemma)
                for k in range(n):
                    by_pos[i + k] = tokens[i + k]
                break
    positions = sorted(by_pos)
    return matched, [by_pos[p] for p in positions], positions


def surface_forms(tokens, query_words, lemmatize=None):
    """Per token, the extra query words it stands for in surface form, for
    the closeness count: a joined token realises each part the query typed
    ("quousque" for "quo usque"), and a run of part tokens realises a joined
    query word. `tokens` and `query_words` are already normalised. For the
    compounds that inflect, pass `lemmatize` and the same is read by lemma
    (iurisiurandi realises "ius iurandum", "iuris iurandi" realises
    "iurisiurandi"). Returns a list of sets, one per token."""
    out = [set() for _ in tokens]
    qwords = set(query_words)
    table = load_table(lemmatize) if lemmatize else {}
    for joined, parts in UNIVERBATIONS_LA.items():
        pf = [fold_latin(p) for p in parts]
        jf = fold_latin(joined)
        entry = table.get(joined)
        if entry is not None and entry.inflecting:
            qlem = {w: frozenset(lemmatize(w)) | {w} for w in qwords}
            typed = [[w for w in qwords if qlem[w] & entry.part_lemmas[k]] for k in range(len(parts))]
            if all(typed):
                words = {w for ws in typed for w in ws}
                for i, t in enumerate(tokens):
                    if t == jf or t in entry.forms:
                        out[i].update(words)
            joined_words = [w for w in qwords if w == jf or w in entry.forms]
            if joined_words:
                n = len(pf)
                tl = [frozenset(lemmatize(t)) | {t} for t in tokens]
                for i in range(len(tokens) - n + 1):
                    if all(tl[i + k] & entry.part_lemmas[k] for k in range(n)):
                        out[i].update(joined_words)
            continue
        if set(pf) <= qwords:
            for i, t in enumerate(tokens):
                if t == jf:
                    out[i].update(pf)
        if jf in qwords:
            n = len(pf)
            for i in range(len(tokens) - n + 1):
                if list(tokens[i:i + n]) == pf:
                    out[i].add(jf)
    return out
