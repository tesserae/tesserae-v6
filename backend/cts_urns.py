"""Passage lookup by CTS URN: the table and the parser the backend uses.

A CTS URN (urn:cts:latinLit:phi0690.phi003:1.1-1.7 is Vergil, Aeneid 1.1 to
1.7) is the citation form Perseus, the Open Greek and Latin repositories,
Scaife and tools such as Nabu use. data/cts_urns.json maps each Latin and Greek
work file to the URN of its work. scripts/corpus/cts_urns.py fills and checks the
table; this module only reads it.

A text key in the table is the whole-work file name ("vergil.aeneid.tess").
A work held only as parts (vergil.eclogues.part.1.tess and so on) has the key it
would have as one file; its part files resolve by the first citation number.
"""
import json
import os
import re
import threading

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE_PATH = os.path.join(REPO, 'data', 'cts_urns.json')
TEXTS_DIR = os.path.join(REPO, 'texts')

# CTS namespace -> Tesserae language code. Everything else has no CTS namespace here.
NAMESPACES = {'latinLit': 'la', 'greekLit': 'grc'}
LANGUAGES = tuple(NAMESPACES.values())

_NAME = r'[A-Za-z0-9_\-]+'
_LOCUS = r'[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*'
URN_RE = re.compile(
    rf'^urn:cts:(?P<ns>[A-Za-z]+):(?P<group>{_NAME})\.(?P<work>{_NAME})'
    rf'(?:\.(?P<version>{_NAME}))?'
    rf'(?::(?P<start>{_LOCUS})(?:-(?P<end>{_LOCUS}))?(?:@[^\s-]*)?)?$')
PART_RE = re.compile(r'^(?P<base>.+?)\.part\.(?P<num>[^.]+)(?:\..*)?\.tess$')


class UrnMalformed(ValueError):
    """The string is not a CTS URN."""


class UrnNotFound(LookupError):
    """A well-formed URN names a work or a place we do not hold."""


def work_key(filename):
    """The table key for any text file: the whole-work name, a part resolved to its work."""
    name = os.path.basename(str(filename or ''))
    if not name.endswith('.tess'):
        name += '.tess'
    m = PART_RE.match(name)
    return m.group('base') + '.tess' if m else name


def parse_urn(urn):
    """urn:cts:<namespace>:<group>.<work>[.<version>][:<passage>[-<passage>]]

    Returns {'namespace', 'language', 'work_urn', 'start', 'end'}. A version
    segment is accepted and ignored. A shorter end ("1.1-7") is completed from
    the start ("1.1-1.7"). Raises UrnMalformed for anything else.
    """
    m = URN_RE.match((urn or '').strip())
    if not m:
        raise UrnMalformed(f'not a CTS URN: {urn!r}. Expected urn:cts:<namespace>:<work>:<passage>, '
                           'for example urn:cts:latinLit:phi0690.phi003:1.1-1.7')
    start, end = m.group('start'), m.group('end')
    if start and end:
        s_parts, e_parts = start.split('.'), end.split('.')
        if len(e_parts) < len(s_parts):
            end = '.'.join(s_parts[:len(s_parts) - len(e_parts)] + e_parts)
    ns = m.group('ns')
    return {'namespace': ns, 'language': NAMESPACES.get(ns),
            'work_urn': f"urn:cts:{ns}:{m.group('group')}.{m.group('work')}",
            'start': start, 'end': end or start}


_lock = threading.Lock()
_cache = {}


def load_table(path=None):
    """The table, re-read when the file changes. {} when it is missing."""
    path = path or TABLE_PATH
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        return {}
    with _lock:
        hit = _cache.get(('table', path))
        if hit and hit[0] == stamp:
            return hit[1]
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        _cache[('table', path)] = (stamp, data)
        return data


def urn_for(language, filename, table=None):
    """The work URN recorded for a text file (a part resolves to its work), or None."""
    table = load_table() if table is None else table
    entry = (table.get(language) or {}).get(work_key(filename))
    return (entry.get('urn') or None) if isinstance(entry, dict) else None


def _by_urn(language, table):
    out = {}
    for key, entry in sorted((table.get(language) or {}).items()):
        if isinstance(entry, dict) and entry.get('urn'):
            out.setdefault(entry['urn'], []).append(key)
    return out


def _files(texts_dir, language):
    """{whole-work key: {'whole': bool, 'parts': {part token: filename}}} for one language folder."""
    d = os.path.join(texts_dir, language)
    try:
        stamp = os.stat(d).st_mtime_ns
    except OSError:
        return {}
    with _lock:
        hit = _cache.get(('files', d))
        if hit and hit[0] == stamp:
            return hit[1]
    found = {}
    for name in os.listdir(d):
        if not name.endswith('.tess'):
            continue
        m = PART_RE.match(name)
        slot = found.setdefault(work_key(name), {'whole': False, 'parts': {}})
        if m:
            slot['parts'].setdefault(m.group('num'), name)
        else:
            slot['whole'] = True
    with _lock:
        _cache[('files', d)] = (stamp, found)
    return found


def lookup(urn, texts_dir=None, table=None):
    """Resolve a CTS URN to (language, filename, locus_start, locus_end).

    The whole-work file is used when there is one. A work held only as parts
    resolves by the first citation number to that part (part.N holds book N);
    a range that crosses parts is not resolved. Raises UrnMalformed or UrnNotFound.
    """
    p = parse_urn(urn)
    if not p['start']:
        raise UrnMalformed(f"{urn!r} names a work, not a passage: add a passage after a colon, "
                           'for example :1.1-1.7')
    language = p['language']
    if language is None:
        raise UrnNotFound(f"no texts under the CTS namespace {p['namespace']!r}: "
                          'Tesserae resolves latinLit and greekLit')
    table = load_table() if table is None else table
    keys = _by_urn(language, table).get(p['work_urn'])
    if not keys:
        raise UrnNotFound(f"no text in Tesserae for {p['work_urn']}")
    files = _files(texts_dir or TEXTS_DIR, language)
    first = p['start'].split('.')[0]
    for key in keys:
        slot = files.get(key)
        if not slot:
            continue
        if slot['whole']:
            return language, key, p['start'], p['end']
        part = slot['parts'].get(first)
        if part is None:
            lettered = [n for tok, n in slot['parts'].items() if tok.rstrip('abcdefgh') == first]
            part = lettered[0] if len(lettered) == 1 else None
        if part is not None:
            if p['end'].split('.')[0] != first:
                raise UrnNotFound(f"{p['work_urn']} is held in parts, and {p['start']}-{p['end']} "
                                  'crosses from one part to another: ask for each part separately')
            return language, part, p['start'], p['end']
        raise UrnNotFound(f"{p['work_urn']} is held in parts and has none for {p['start']}")
    raise UrnNotFound(f"{p['work_urn']} is in the table but its text file is not on this server")
