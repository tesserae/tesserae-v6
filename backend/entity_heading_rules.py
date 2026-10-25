"""Headings for People & Places names that were built from running text: the nominative a heading should carry.

The builder (entity_promote.best_form) weights a count by the ending of the form, so an oblique form that is
several times commoner than the nominative, or a neuter-looking -um accusative (Childeberthum for the king named
Childeberthus), can become the heading. propose() reads the spellings under one entity and returns the
nominative to use, with the spellings the decision rested on, when a rule applies:

  * the heading is a Latin or Greek form whose ending is an oblique case of the second declension or an
    accusative of the first (a plural-looking -ae or -as is left alone: Athenae is a name as it stands),
  * the nominative of the same stem occurs among the entity's own spellings.

Where the heading does not end in -us or -ος and no rule applies, the result is ('ASK', None, ...) and the caller
asks the model (many such headings are right: Athenae, a Greek -ης name). A heading ending in -us or -ος returns
None.
"""
import unicodedata

from backend import entity_promote as pr

# Latin: (oblique ending, nominative endings of the same stem). Longest ending first. Neuter -um and -on are
# nominatives too, so they count as oblique only when the -us / -os nominative of the stem is attested.
LATIN = [
    ('orum', ('us',)), ('arum', ('a',)), ('ibus', ()), ('iis', ('ius',)),
    ('um', ('us',)), ('os', ('us',)), ('is', ('us',)), ('am', ('a',)),
    ('i', ('us',)), ('o', ('us',)),
]
GREEK = [
    ('οις', ('ος',)), ('ους', ('ος',)), ('ου', ('ος',)), ('ον', ('ος',)), ('ῳ', ('ος',)), ('ην', ('η',)),
    ('ῃ', ('η',)),
]
# Endings that need no check for a nominative to be believed oblique (never a nominative of a name).
SURE = ('orum', 'arum', 'ibus', 'iis', 'ου', 'οις', 'ους', 'ῳ')


def _plain(s):
    return pr._plain(s)


def _readings(heading, script):
    """[(stem, nominative endings, ending)] for each oblique ending the heading carries, longest first."""
    h = _plain(heading)
    table = LATIN if script == 'latin' else GREEK
    out = []
    for end, noms in table:
        e = _plain(end)
        if h.endswith(e) and len(h) - len(e) >= 3:
            out.append((h[:-len(e)], tuple(_plain(n) for n in noms), e))
    return out


def propose(heading, forms):
    """forms: {spelling: rows}. Returns None when the heading needs no change, else (rule, new heading or None,
    evidence list). rule is 'rule' when a nominative of the stem is among the spellings, 'ASK' when the heading
    looks oblique and none is."""
    script = pr.script_of(heading)
    if script not in ('latin', 'greek'):
        return None
    reads = _readings(heading, script)
    if not reads:
        if looks_nominative(heading):
            return None
        pool = {f: n for f, n in forms.items() if pr.script_of(f) == script}
        ev = sorted(pool.items(), key=lambda x: (-x[1], x[0]))[:6]
        return ('ASK', None, [f'{f} {n}' for f, n in ev])
    pool = {f: n for f, n in forms.items() if pr.script_of(f) == script}
    for stem, noms, end in reads:
        found = {f: n for f, n in pool.items() if any(_plain(f) == stem + nom for nom in noms) and _plain(f) != _plain(heading)}
        if found:
            best = max(found, key=lambda f: (found[f], f))
            ev = sorted(pool.items(), key=lambda x: (-x[1], x[0]))[:6]
            return ('rule', best, [f'{f} {n}' for f, n in ev])
    stem, noms, end = reads[0]
    ev = sorted(pool.items(), key=lambda x: (-x[1], x[0]))[:6]
    return ('ASK', None, [f'{f} {n}' for f, n in ev])


def looks_nominative(heading):
    """True for the endings that are nominative singular of a name beyond doubt (-us, Greek -ος): no check."""
    h = _plain(heading)
    return h.endswith(('us', 'οσ'))


def nfc(s):
    return unicodedata.normalize('NFC', s)
