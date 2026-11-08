"""License class and credit line for any text in the corpus.

One lookup used by the Reader's About panel (through corpus._work_facts) and
by every connector tool that returns a text or a passage.

The source of truth is backend/text_sources.json (one row per work: author,
work, e_source, e_source_url, print_source, license) and, for a text held
under an indexing-only licence, data/restricted_texts.json (backend/
restricted_texts.py). A work's row is found by lowercased author plus work
display strings, the way the Sources page keys an entry (there is no id the
two files share).

lookup_by_file / lookup_by_names return
    {"license": <class>, "license_label": <words>, "license_text": <row string>,
     "credit": <one line>}
where <class> is one of CLASSES.
"""
import re

from backend import restricted_texts

CLASSES = (
    'public-domain', 'cc-by', 'cc-by-sa', 'cc-by-nc', 'cc-by-nc-sa',
    'noncommercial', 'academic-only', 'restricted', 'unknown',
)

# Ordered rules: the first pattern found in the lowercased license string
# decides. More restrictive terms come before more permissive ones, because a
# string that carries both (for example "academic use only; CC-BY-SA 4.0")
# binds the reader to the stricter one. Each row has a test in
# tests/test_text_license.py.
_CC = r'cc[\s-]*by'
CLASS_RULES = (
    # 1. A source whose terms were not verified is not classed by what it
    #    names, only by what it states of itself.
    ('unverified-upstream', r'^the classical text is public domain\..*not independently verified', 'unknown'),
    # 2. Academic use only (Wells, Sahidica).
    ('academic-only', r'academic use only', 'academic-only'),
    # 3. Creative Commons with NonCommercial.
    ('cc-by-nc-sa', _CC + r'[\s-]*nc[\s-]*sa', 'cc-by-nc-sa'),
    ('cc-by-nc', _CC + r'[\s-]*nc', 'cc-by-nc'),
    # 4. Other noncommercial terms (Musisque Deoque).
    ('noncommercial', r'non-?commercial', 'noncommercial'),
    # 5. All rights reserved with no license stated.
    ('all-rights-reserved', r'all rights reserved', 'restricted'),
    # 6. Creative Commons with ShareAlike, then plain Attribution.
    ('cc-by-sa', _CC + r'[\s-]*sa\b', 'cc-by-sa'),
    ('cc-by', _CC + r'(?![\s-]*(?:sa|nc|nd)\b)', 'cc-by'),
    # 7. Public domain.
    ('public-domain', r'public[\s-]*domain', 'public-domain'),
)
_COMPILED = tuple((name, re.compile(rx), cls) for name, rx, cls in CLASS_RULES)

CLASS_WORDS = {
    'public-domain': 'Public domain',
    'cc-by': 'CC BY',
    'cc-by-sa': 'CC BY-SA',
    'cc-by-nc': 'CC BY-NC',
    'cc-by-nc-sa': 'CC BY-NC-SA',
    'noncommercial': 'Noncommercial use only',
    'academic-only': 'Academic use only',
    'restricted': 'Restricted',
    'unknown': 'Not stated',
}

_VERSION = re.compile(r'\bcc[\s-]*by(?:[\s-]*nc)?(?:[\s-]*sa)?\s+(\d\.\d(?:\s+(?:us|it)\b)?)')


def classify(license_string):
    """(class, rule name) for a license string. Empty or 'unknown' is unknown."""
    s = (license_string or '').strip().lower()
    if not s or s == 'unknown':
        return 'unknown', 'empty-or-unknown'
    for name, rx, cls in _COMPILED:
        if rx.search(s):
            return cls, name
    return 'unknown', 'no-rule'


def license_class(license_string):
    return classify(license_string)[0]


def license_label(license_string, cls=None):
    """The class in words, with the version when the string states one
    directly after the license name ("CC BY-SA 4.0", "CC BY-NC-SA 3.0 IT")."""
    cls = cls or license_class(license_string)
    words = CLASS_WORDS[cls]
    if cls.startswith('cc-'):
        m = _VERSION.search((license_string or '').lower())
        if m:
            version = m.group(1).split()
            words += ' ' + ' '.join([version[0]] + [v.upper() for v in version[1:]])
    return words


def _clean(s):
    return (s or '').strip().rstrip('.;, ')


def credit_line(row):
    """One line: the digital source, then the print edition when present."""
    parts = [_clean(row.get('e_source')), _clean(row.get('print_source'))]
    parts = [p for p in parts if p]
    return '. '.join(parts) + '.' if parts else None


# ---------------------------------------------------------------- matching

_index_cache = {'rows_id': None, 'index': {}}


def _rows():
    # Lazy import: corpus owns the mtime-keyed loader of text_sources.json
    # (tests patch it there), and imports this module for _work_facts.
    from backend.blueprints.corpus import get_text_sources
    return get_text_sources()


def _key(author, work):
    return ((author or '').strip().lower(), (work or '').strip().lower())


def find_source_row(author, work, rows=None):
    """The text_sources.json row for this author and work display strings,
    or None. The first row wins, as it always did in _work_facts."""
    if not (author or '').strip() or not (work or '').strip():
        return None
    if rows is None:
        rows = _rows()
    if _index_cache['rows_id'] is not rows:
        index = {}
        for row in rows:
            index.setdefault(_key(row.get('author'), row.get('work')), row)
        _index_cache['index'] = index
        _index_cache['rows_id'] = rows
    return _index_cache['index'].get(_key(author, work))


# ----------------------------------------------------------------- lookups

_UNKNOWN = {'license': 'unknown', 'license_label': CLASS_WORDS['unknown'],
            'license_text': None, 'credit': None}


def from_row(row):
    """The lookup result for one text_sources.json row."""
    text = row.get('license')
    cls = license_class(text)
    return {'license': cls, 'license_label': license_label(text, cls),
            'license_text': text, 'credit': credit_line(row)}


def lookup_by_names(author, work):
    row = find_source_row(author, work)
    return from_row(row) if row else dict(_UNKNOWN)


def lookup_by_file(filename_or_id, language=None):
    """By a text filename or work id (vergil.aeneid, vergil.aeneid.tess,
    vergil.aeneid.part.3.tess, la/vergil.aeneid.tess). A restricted text
    answers from the registry. Language is accepted for symmetry with the
    other lookups; ids are unique across languages."""
    name = (filename_or_id or '').strip()
    if not name:
        return dict(_UNKNOWN)
    if restricted_texts.is_restricted(name):
        return {'license': 'restricted', 'license_label': CLASS_WORDS['restricted'],
                'license_text': restricted_texts.license_for(name),
                'credit': restricted_texts.credit_for(name)}
    from backend.utils import get_text_metadata
    base = name.rsplit('/', 1)[-1]
    if not base.endswith('.tess'):
        base += '.tess'
    meta = get_text_metadata(base)
    return lookup_by_names(meta.get('author'), meta.get('work') or meta.get('title'))


def fields(result):
    """The two fields every connector payload carries."""
    return {'license': result['license'], 'credit': result['credit']}


def class_counts(rows=None):
    """Rows per class, and the distinct strings that fall to unknown."""
    rows = _rows() if rows is None else rows
    counts = {c: 0 for c in CLASSES}
    unknown = {}
    for row in rows:
        cls = license_class(row.get('license'))
        counts[cls] += 1
        if cls == 'unknown':
            unknown[row.get('license')] = unknown.get(row.get('license'), 0) + 1
    return counts, unknown
