"""What this server holds, read from its own state (2026-10-10).

Tessa's description of the site used to be a fixed sentence in her prompt
("Latin, Greek, Hebrew, English and Coptic literature"), which went stale as
Persian, Urdu, the inscriptions and papyri, the scholarship and the events
were added. Owner's review of 10 October: the site should not need her
updated by hand every time it changes. So the sentence is built here from
the same checks the site itself makes: the language flags and text folders
that /api/languages reads, the served-languages allow-list, the documents
indexes, the scholarship data and the dossier databases. Cached for ten
minutes so a request never pays for the folder checks twice.
"""
import os
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TTL = 600

# (code, label, flag module, flag name). Latin, Greek and English are always
# present; the rest are served when their flag is on and their folder exists,
# exactly as /api/languages decides it (backend/app.py api_languages).
_OPTIONAL = (
    ('cop', 'Coptic', 'backend.coptic', 'COPTIC_ENABLED'),
    ('he', 'Hebrew', 'backend.hebrew', 'HEBREW_ENABLED'),
    ('fa', 'Persian', 'backend.persian', 'PERSIAN_ENABLED'),
    ('ur', 'Urdu', 'backend.urdu', 'URDU_ENABLED'),
    ('ar', 'Arabic', 'backend.arabic', 'ARABIC_ENABLED'),
)


def _flag(module, name):
    try:
        mod = __import__(module, fromlist=[name])
        return bool(getattr(mod, name, False))
    except ImportError:
        return False


def languages():
    """[(code, label)] for the languages this server serves, in tab order."""
    out = [('la', 'Latin'), ('grc', 'Greek'), ('en', 'English')]
    for code, label, module, name in _OPTIONAL:
        if _flag(module, name) and os.path.isdir(os.path.join(_ROOT, 'texts', code)):
            out.append((code, label))
    try:
        from backend.served_languages import allowed_languages
        allowed = allowed_languages()
    except ImportError:
        allowed = None
    if allowed:
        order = [x.strip() for x in os.environ.get('TESSERAE_LANGUAGES', '').split(',') if x.strip()]
        out = sorted((l for l in out if l[0] in allowed), key=lambda l: order.index(l[0]))
    return out


def collections():
    """[(key, description)] for the collections beyond the literature that
    this server has data for. Each check is the one the feature's own
    route makes before it answers."""
    out = []
    try:
        import backend.documents as docs
        if docs.enabled() and any(docs.is_index_available(l) for l in docs.SUPPORTED_LANGUAGES):
            out.append(('documents', 'inscriptions and papyri in Latin and Greek (searchable '
                                     'with the literature or on their own)'))
    except ImportError:
        pass
    try:
        from backend import scholarship as sch
        has_comm = os.path.isdir(sch.COMMENTARY_DIR) and any(
            True for _ in os.scandir(sch.COMMENTARY_DIR))
        if has_comm or os.path.exists(sch.CITATION_INDEX):
            out.append(('scholarship', 'secondary scholarship on each passage (public-domain '
                                       'commentaries, a citation index of early journal '
                                       'articles and live lookups of articles and books)'))
    except ImportError:
        pass
    try:
        from backend.blueprints import events as ev
        if os.path.exists(ev.db_path()):
            out.append(('events', 'historical events (battles, sieges, campaigns and treaties, '
                                  'each with the passages that tell of it, the inscriptions '
                                  'and papyri from nearby and the scholarship)'))
    except ImportError:
        pass
    coins = os.environ.get('TESSERAE_COINS_DB') or os.path.join(_ROOT, 'data', 'coins', 'coins.sqlite')
    if os.path.exists(coins):
        out.append(('coins', 'Roman coin types with their legends and descriptions'))
    objects = os.environ.get('TESSERAE_OBJECTS_DB') or os.path.join(_ROOT, 'data', 'objects', 'objects.sqlite')
    if os.path.exists(objects):
        out.append(('objects', 'museum objects with the catalogue descriptions of the Cleveland Museum '
                               'of Art, the Art Institute of Chicago and the Smithsonian'))
    return out


def _join(names):
    names = list(names)
    if len(names) <= 1:
        return ''.join(names)
    return ', '.join(names[:-1]) + ' and ' + names[-1]


def build_holdings_sentence():
    langs = _join(label for _, label in languages())
    text = (f'Tesserae holds literature in {langs} and finds intertextual parallels '
            '(quotations, allusions, echoes, borrowings) within and across those languages.')
    cols = collections()
    if cols:
        text += (' This site also holds ' + _join(d for _, d in cols) + '. These collections are '
                 'switched on through the Collections control in the menu bar (the Historical '
                 'profile), and are in testing.')
    return text


_cache = {'at': 0.0, 'text': None}


def holdings_sentence():
    """The current description, rebuilt at most every ten minutes. A sentence
    that names no optional language is not cached: it is what the checks give
    before the language plugins have registered (app start-up), and on
    2026-10-10 a copy cached then stood for the whole day."""
    now = time.time()
    if _cache['text'] is None or now - _cache['at'] > _TTL:
        text = build_holdings_sentence()
        if len(languages()) <= 3:
            return text
        _cache['text'] = text
        _cache['at'] = now
        return text
    return _cache['text']


def reset_cache():
    _cache['text'] = None
    _cache['at'] = 0.0
