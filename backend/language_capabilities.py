"""What the site can do in each language it serves, read cheaply from the installed stores.

    GET /api/scope/capabilities  (route in backend/blueprints/scope.py)

Twelve capabilities, one reader function each. Every reader says in its docstring
which file it reads, takes the language code and the shared facts (`ctx`), and
returns {"state": "full" | "partial" | "none", "count": int | None, "note": str}.
Nothing here rebuilds or writes anything. A later import-procedure step can be
"check the capabilities table": the answer lists the same twelve for every language.
"""
import csv
import glob
import json
import os
import sqlite3

from backend.logging_config import get_logger
from backend.work_names import base_work

logger = get_logger('language_capabilities')

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (key, short heading, long name), in table order.
CAPABILITIES = [
    ('texts', 'Texts', 'Texts'),
    ('lemmas', 'Dictionary forms', 'Line Search with dictionary forms'),
    ('syntax', 'Grammar parse', 'Grammar parse'),
    ('meter', 'Scansion', 'Scansion (meter)'),
    ('windows', 'Passages', 'Passage windows and descriptions'),
    ('names', 'Names & places', 'Window names and People & Places'),
    ('translations', 'Translations', 'Translations'),
    ('reuse', 'Reuse marks', 'Reuse table'),
    ('map', 'Connection map', 'Connection map'),
    ('documents', 'Documents', 'Documents (inscriptions and papyri)'),
    ('dictionary', 'Dictionary lookup', 'Dictionary lookup'),
    ('crosslingual', 'Cross-language', 'Cross-language search'),
]

SYNTAX_DB = {'la': 'syntax_latin.db', 'grc': 'syntax_greek.db', 'cop': 'syntax_coptic.db'}
LEMMA_TABLES = {
    'la': ('latin_lemmas.json',), 'grc': ('greek_lemmas.json',), 'cop': ('coptic_lemmas.json',),
    'he': ('hebrew_lemmas.json',), 'fa': ('fa_surface_lemmas.json',), 'ur': ('ur_surface_lemmas.json',),
    'ar': ('ar_surface_lemmas.json',),
}
VERSE_METERS = ('hexameter', 'elegiac', 'lyric', 'dramatic', 'mixed')


def _cell(state, count=None, note=''):
    return {'state': state, 'count': count, 'note': note}


def _not_read():
    return _cell('none', None, 'not read')


def _share(have, total):
    return f'{have} of {total}'


def _ro(path):
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


def _tess_files(lang):
    try:
        return {f for f in os.listdir(os.path.join(_ROOT, 'texts', lang)) if f.endswith('.tess')}
    except OSError:
        return set()


def _read_json(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _lang_of(wid, work_lang):
    """Language of a window id '<work>:<kind>:<n>'; a part ('x.part.5') falls back to its whole work."""
    work = wid.rsplit(':', 2)[0]
    lang = work_lang.get(work)
    if lang is None:
        lang = work_lang.get(base_work(work))
    return lang


def _window_counts():
    """{language: windows} from data/passage_index/ids.json, each id's work
    (the part before the last two colons) looked up in works_by_language.json."""
    pdir = os.path.join(_ROOT, 'data', 'passage_index')
    ids = _read_json(os.path.join(pdir, 'ids.json'))
    wbl = _read_json(os.path.join(pdir, 'works_by_language.json'))
    if not ids or not wbl:
        return None
    work_lang = {}
    for lang, works in (wbl.get('languages') or {}).items():
        for w in works:
            work_lang[w] = lang
    out = {}
    for wid in ids:
        lang = _lang_of(wid, work_lang)
        if lang:
            out[lang] = out.get(lang, 0) + 1
    return out


def _name_counts():
    """{language: windows with names} from data/passage_index/window_names.db (distinct ids)."""
    pdir = os.path.join(_ROOT, 'data', 'passage_index')
    path = os.path.join(pdir, 'window_names.db')
    wbl = _read_json(os.path.join(pdir, 'works_by_language.json'))
    if not os.path.exists(path) or not wbl:
        return None
    work_lang = {w: lang for lang, ws in (wbl.get('languages') or {}).items() for w in ws}
    out = {}
    c = _ro(path)
    try:
        for (wid,) in c.execute('SELECT DISTINCT id FROM window_names'):
            lang = _lang_of(wid, work_lang)
            if lang:
                out[lang] = out.get(lang, 0) + 1
    finally:
        c.close()
    return out


def _entity_counts():
    """{language: windows with entities} from data/entity_index/entities.sqlite (windows table)."""
    path = os.path.join(_ROOT, 'data', 'entity_index', 'entities.sqlite')
    if not os.path.exists(path):
        return None
    c = _ro(path)
    try:
        return dict(c.execute('SELECT language, COUNT(*) FROM windows GROUP BY language'))
    finally:
        c.close()


def _map_counts():
    """{language: works} from the newest cache/connections_map/*.db (works table)."""
    files = sorted(glob.glob(os.path.join(_ROOT, 'cache', 'connections_map', '*.db')), key=os.path.getmtime)
    if not files:
        return None
    c = _ro(files[-1])
    try:
        return dict(c.execute('SELECT language, COUNT(*) FROM works GROUP BY language'))
    finally:
        c.close()


def _translation_counts():
    """{language: works with an aligned translation}: file names '<lang>__<work>.json' in data/translations."""
    d = os.path.join(_ROOT, 'data', 'translations')
    out = {}
    try:
        names = os.listdir(d)
    except OSError:
        return None
    for n in names:
        if n.endswith('.json') and '__' in n and n != 'manifest.json':
            lang = n.split('__', 1)[0]
            out[lang] = out.get(lang, 0) + 1
    return out


def _latin_verse_files():
    """Latin files with a verse meter in data/text_genres.csv."""
    path = os.path.join(_ROOT, 'data', 'text_genres.csv')
    try:
        with open(path, encoding='utf-8', newline='') as fh:
            return {r['filename'] for r in csv.DictReader(fh) if r.get('meter') in VERSE_METERS}
    except (OSError, KeyError):
        return None


def make_context(languages, pairs, held):
    """The shared facts, each read once: languages = [{'code','label'}], pairs and held as /api/languages gives them."""
    def safe(fn):
        try:
            return fn()
        except Exception:                                           # noqa: BLE001
            logger.warning('[CAPABILITIES] %s failed', fn.__name__, exc_info=True)
            return None
    return {
        'windows': safe(_window_counts), 'names': safe(_name_counts), 'entities': safe(_entity_counts),
        'map': safe(_map_counts), 'translations': safe(_translation_counts),
        'verse': safe(_latin_verse_files), 'pairs': pairs or [], 'held': held or [],
    }


def read_texts(lang, ctx):
    """Reads texts/<lang>/*.tess (file names only)."""
    n = len(_tess_files(lang))
    return _cell('full' if n else 'none', n, f'{n} text files' if n else 'no texts')


def read_lemmas(lang, ctx):
    """Reads data/lemma_tables/<name>.json and counts cache/lemmas/<lang>/ files against the text files."""
    cache = os.path.join(_ROOT, 'cache', 'lemmas', lang)
    try:
        n = len([f for f in os.listdir(cache) if not f.startswith('.')])
    except OSError:
        n = 0
    table = any(os.path.exists(os.path.join(_ROOT, 'data', 'lemma_tables', t)) for t in LEMMA_TABLES.get(lang, ()))
    if not n and not table:
        return _cell('none', 0, 'no lemma table or cache')
    total = len(_tess_files(lang))
    if total and n < total:
        return _cell('partial', n, _share(n, total) + ' texts have dictionary forms')
    return _cell('full', n, 'every text has dictionary forms')


def read_syntax(lang, ctx):
    """Reads data/inverted_index/<syntax_*.db> (texts table, filename column), named in SYNTAX_DB."""
    name = SYNTAX_DB.get(lang)
    if not name:
        return _cell('none', 0, 'no parser for this language')
    path = os.path.join(_ROOT, 'data', 'inverted_index', name)
    if not os.path.exists(path):
        return _cell('none', 0, 'no parse database')
    c = _ro(path)
    try:
        parsed = {r[0] for r in c.execute('SELECT DISTINCT filename FROM texts')}
    finally:
        c.close()
    files = _tess_files(lang)
    have = len(parsed & files)
    if not have:
        return _cell('none', 0, 'no texts parsed')
    if have >= len(files):
        return _cell('full', have, 'every text parsed')
    return _cell('partial', have, _share(have, len(files)) + ' texts parsed')


def read_meter(lang, ctx):
    """Reads data/text_genres.csv (meter column); Latin verse only today."""
    if lang != 'la':
        return _cell('none', 0, 'Latin verse only so far')
    verse = ctx.get('verse')
    if verse is None:
        return _not_read()
    n = len(verse & _tess_files('la'))
    return _cell('full' if n else 'none', n, f'{n} verse texts with a meter' if n else 'no verse texts')


def read_windows(lang, ctx):
    """Reads data/passage_index/ids.json with works_by_language.json (windows per language)."""
    counts = ctx.get('windows')
    if counts is None:
        return _not_read()
    n = counts.get(lang, 0)
    return _cell('full' if n else 'none', n, f'{n} passage windows' if n else 'no passage windows')


def read_names(lang, ctx):
    """Reads data/passage_index/window_names.db and data/entity_index/entities.sqlite (windows table)."""
    names, ents = ctx.get('names'), ctx.get('entities')
    if names is None and ents is None:
        return _not_read()
    n, e = (names or {}).get(lang, 0), (ents or {}).get(lang, 0)
    if n and e:
        return _cell('full', e, f'{n} windows named, {e} with people and places')
    if n or e:
        which = 'names only' if n else 'people and places only'
        return _cell('partial', e or n, which)
    return _cell('none', 0, 'no names or entities')


def read_translations(lang, ctx):
    """Reads the file names in data/translations ('<lang>__<work>.json') against the text files."""
    counts = ctx.get('translations')
    if counts is None:
        return _not_read()
    n = counts.get(lang, 0)
    total = len(_tess_files(lang))
    if not n:
        return _cell('none', 0, 'no aligned translations')
    if total and n < total:
        return _cell('partial', n, _share(n, total) + ' texts have a translation')
    return _cell('full', n, 'every text has a translation')


def read_reuse(lang, ctx):
    """Reads whether cache/reuse_pairs/<lang>.db exists."""
    ok = os.path.exists(os.path.join(_ROOT, 'cache', 'reuse_pairs', f'{lang}.db'))
    return _cell('full' if ok else 'none', None, 'reuse table built' if ok else 'no reuse table')


def read_map(lang, ctx):
    """Reads the works table of the newest cache/connections_map/*.db."""
    counts = ctx.get('map')
    if counts is None:
        return _not_read()
    n = counts.get(lang, 0)
    return _cell('full' if n else 'none', n, f'{n} works on the map' if n else 'not on the map')


def read_documents(lang, ctx):
    """Reads backend.documents (SUPPORTED_LANGUAGES, is_index_available) and its doc_meta count."""
    try:
        import backend.documents as docs
        if not docs.enabled() or lang not in docs.SUPPORTED_LANGUAGES or not docs.is_index_available(lang):
            return _cell('none', 0, 'no documents collection')
        con = _ro(docs._index_db_path(lang))
        try:
            n = int(con.execute('SELECT COUNT(*) FROM doc_meta').fetchone()[0])
        finally:
            con.close()
        return _cell('full' if n else 'none', n, f'{n} documents')
    except Exception:                                               # noqa: BLE001
        return _not_read()


def read_dictionary(lang, ctx):
    """Reads backend.blueprints.define (LOGEION_DICTIONARIES, EXTERNAL_DICTIONARIES) and
    data/lemma_tables/greek_headwords.json: full where the site shows entries itself,
    partial where it links out to a dictionary site."""
    try:
        from backend.blueprints import define
    except ImportError:
        return _not_read()
    if lang in define.LOGEION_DICTIONARIES:
        if lang == 'grc' and not os.path.exists(os.path.join(_ROOT, 'data', 'lemma_tables', 'greek_headwords.json')):
            return _cell('partial', None, 'entries shown, headword table missing')
        return _cell('full', len(define.LOGEION_DICTIONARIES[lang]), 'entries shown on the site')
    if lang in define.EXTERNAL_DICTIONARIES:
        return _cell('partial', None, 'links to ' + define.EXTERNAL_DICTIONARIES[lang][0])
    return _cell('none', None, 'no dictionary')


def read_crosslingual(lang, ctx):
    """Reads the pairs and held pairs /api/languages answers: full when a pair with this language is served,
    partial when every pair is held (the held reason is the note)."""
    live = [p for p in ctx['pairs'] if lang in (p.get('source'), p.get('target'))]
    if live:
        return _cell('full', len(live), 'pairs: ' + ', '.join(p.get('label', p.get('key', '')) for p in live))
    held = [h for h in ctx['held'] if lang in str(h.get('key', '')).split('-')]
    if held:
        return _cell('partial', len(held), 'held: ' + str(held[0].get('reason', '')))
    return _cell('none', 0, 'no cross-language pair')


READERS = {
    'texts': read_texts, 'lemmas': read_lemmas, 'syntax': read_syntax, 'meter': read_meter,
    'windows': read_windows, 'names': read_names, 'translations': read_translations,
    'reuse': read_reuse, 'map': read_map, 'documents': read_documents,
    'dictionary': read_dictionary, 'crosslingual': read_crosslingual,
}


def build(languages, pairs=None, held=None, readers=None):
    """The whole answer: capabilities (key, heading, name) and one row per language."""
    readers = readers or READERS
    ctx = make_context(languages, pairs, held)
    rows = []
    for lang in languages:
        cells = {}
        for key, _short, _long in CAPABILITIES:
            try:
                cells[key] = readers[key](lang['code'], ctx)
            except Exception:                                       # noqa: BLE001
                logger.warning('[CAPABILITIES] %s/%s failed', lang['code'], key, exc_info=True)
                cells[key] = _not_read()
        rows.append({'code': lang['code'], 'label': lang['label'], 'capabilities': cells})
    return {'capabilities': [{'key': k, 'heading': s, 'name': n} for k, s, n in CAPABILITIES], 'languages': rows}
