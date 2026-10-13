"""Site-wide information routes: health, version, languages, stats, check-meter, author dates.

Moved out of backend/app.py unchanged (application-factory job, 2026-10-12).
"""
import os

from flask import Blueprint, jsonify, request

from backend.cache import get_cache_stats
from backend.runtime import (
    STATIC_FOLDER, TEXTS_DIR, AUTHOR_DATES,
    app_logger, api_route_for,
)

meta_bp = Blueprint('meta', __name__)

# Cross-language pairs held back from the site until their data is rebuilt;
# key -> the plain reason shown on the page. Empty when nothing is held.
CROSSLINGUAL_HELD = {
    'la-en': 'Latin to English searches are offline while the English texts are re-embedded '
             'in the same space as the Latin and Greek ones; they return when that is done.',
    'grc-en': 'Greek to English searches are offline while the English texts are re-embedded '
              'in the same space as the Latin and Greek ones; they return when that is done.',
}
api_route = api_route_for(meta_bp)

# api_languages() finds the texts folder as dirname(dirname(__file__)), which was the
# repository root when this code lived in backend/app.py. Keep that meaning here.
__file__ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.py')

# -----------------------------------------------------------------------------
# CACHING: never the page, forever the assets
# -----------------------------------------------------------------------------
# index.html goes out with no Cache-Control, only an ETag, so browsers fall back
# to heuristic caching and can serve a stale page for hours without asking. Every
# deploy renames the bundle, so a stale page asks for a file that no longer
# exists: the app fails to load and the reader sees a blank panel, or a blank
# site. That happened twice in one day.
#
# THIS HOOK CANNOT FIX THAT ON THE CURRENT DEPLOYMENT, and saying so here is the
# point. Apache mounts Flask at /api only (WSGIScriptAlias /api) and serves the
# page and /assets/ itself from DocumentRoot, so these headers never reach them.
# An .htaccess is ignored too: the <Directory> block sets no AllowOverride.
#
# The real fix is three lines in the vhost, and needs root:
#
#   <Directory /var/www/tess-new>
#     <FilesMatch "\.html$">  Header set Cache-Control "no-cache, must-revalidate"  </FilesMatch>
#     <FilesMatch "\.(js|css|woff2?)$">  Header set Cache-Control "public, max-age=31536000, immutable"  </FilesMatch>
#   </Directory>
#
# The hook is kept because it is correct for anything Flask does serve, and
# because it will start covering the page the day the mount changes.
# -----------------------------------------------------------------------------
# WHICH BUILD IS CURRENT
# -----------------------------------------------------------------------------
# So a running page can notice it is out of date and offer to reload.
#
# The failure this addresses is quiet and nasty. Apache falls back to index.html
# for any path it cannot find, so a stale page asking for a bundle that no longer
# exists gets 200 OK with Content-Type text/html: the PAGE, pretending to be
# JavaScript. The browser tries to execute HTML, fails at parse, and nothing
# runs at all -- no app, no error handler, no message. Just a dead panel.
_BUILD = {'name': None, 'checked': 0.0}


# =============================================================================
# HEALTH CHECK ROUTES
# =============================================================================

@meta_bp.route('/health')
def health():
    """Basic health check endpoint"""
    return jsonify({"status": "ok", "message": "Tesserae V6 is running"})


def _current_bundle():
    """The JS bundle a fresh visitor would be served.

    Lets a running page notice it is out of date. Apache falls back to
    index.html for any path it cannot find, so a stale page asking for a
    deleted bundle gets 200 with Content-Type text/html -- the page pretending
    to be JavaScript -- and nothing runs at all.
    """
    import re as _re
    import time as _time
    now = _time.time()
    if not _BUILD['name'] or now - _BUILD['checked'] > 30:
        try:
            with open(os.path.join(STATIC_FOLDER, 'index.html'), encoding='utf-8') as fh:
                head = fh.read(8192)
            m = _re.search(r'/assets/(index-[A-Za-z0-9_-]+\.js)', head)
            _BUILD['name'] = m.group(1) if m else None
        except OSError:
            _BUILD['name'] = None
        _BUILD['checked'] = now
    return _BUILD['name']




@api_route('/health')
def api_health():
    """API health check endpoint"""
    return jsonify({"status": "ok", "message": "Tesserae V6 is running"})


def _current_bundle():
    """The JS bundle a fresh visitor would be served.

    Lets a running page notice it is out of date. Apache falls back to
    index.html for any path it cannot find, so a stale page asking for a
    deleted bundle gets 200 with Content-Type text/html -- the page pretending
    to be JavaScript -- and nothing runs at all.
    """
    import re as _re
    import time as _time
    now = _time.time()
    if not _BUILD['name'] or now - _BUILD['checked'] > 30:
        try:
            with open(os.path.join(STATIC_FOLDER, 'index.html'), encoding='utf-8') as fh:
                head = fh.read(8192)
            m = _re.search(r'/assets/(index-[A-Za-z0-9_-]+\.js)', head)
            _BUILD['name'] = m.group(1) if m else None
        except OSError:
            _BUILD['name'] = None
        _BUILD['checked'] = now
    return _BUILD['name']
@api_route('/version')
def api_version():
    """Get version and last updated info from git"""
    import subprocess
    try:
        # Get last commit date in ISO format
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%ci'],
            capture_output=True, text=True, timeout=5
        )
        last_updated = result.stdout.strip() if result.returncode == 0 else None
        
        # Format as readable date (e.g., "January 27, 2026")
        if last_updated:
            from datetime import datetime
            dt = datetime.strptime(last_updated[:19], '%Y-%m-%d %H:%M:%S')
            formatted_date = dt.strftime('%B %d, %Y')
        else:
            formatted_date = None
            
        return jsonify({
            "version": "6.0",
            "last_updated": formatted_date,
            "last_updated_raw": last_updated,
            # The JS bundle a fresh visitor gets, so a running page can notice
            # it is stale and offer to reload.
            "bundle": _current_bundle(),
        })
    except Exception as e:
        app_logger.error(f"Error getting version info: {e}")
        return jsonify({"version": "6.0", "last_updated": None,
                        "bundle": _current_bundle()})


def _allowed_languages():
    """Optional allow-list from TESSERAE_LANGUAGES (comma-separated codes).
    A preview machine that holds only some languages' indexes sets it so the
    site never offers, or tries to list, a language it cannot serve (2026-09-06:
    the preview's home page hung on the Latin text list)."""
    from backend.served_languages import allowed_languages
    return allowed_languages()


@api_route('/corpus-version')
def api_corpus_version():
    """The corpus version stamp (a date) for one language, for citations that
    name the corpus state a result came from (the Cite popup's Reproducible
    style). Read per process; an index change is picked up on reload."""
    language = (request.args.get('language') or 'la').strip()
    try:
        from backend.inverted_index import get_corpus_version
        v = get_corpus_version(language)
    except Exception:
        v = None
    return jsonify({'language': language, 'corpus_version': v})


@api_route('/languages')
def api_languages():
    """Return available languages and cross-lingual pairs.
    Frontend uses this to dynamically populate language tabs."""
    import os
    languages = [
        {'code': 'la', 'label': 'Latin'},
        {'code': 'grc', 'label': 'Greek'},
        {'code': 'en', 'label': 'English'},
    ]
    crosslingual_pairs = [
        {'key': 'grc-la', 'source': 'grc', 'target': 'la', 'label': 'Greek → Latin'},
        {'key': 'la-en', 'source': 'la', 'target': 'en', 'label': 'Latin → English'},
        {'key': 'grc-en', 'source': 'grc', 'target': 'en', 'label': 'Greek → English'},
    ]
    # Pairs held back from the page, with the reason shown to the reader
    # (2026-10-13): the English passage embeddings were built with a
    # different model from the Latin and Greek ones (384 against 768
    # dimensions), so a Latin-English or Greek-English search cannot run
    # until the English texts are re-embedded in the same space. The pairs
    # come back when that is done. Keep this dict empty when nothing is held.
    held = [{'key': k, 'reason': reason} for k, reason in CROSSLINGUAL_HELD.items()]
    try:
        from backend.coptic import COPTIC_ENABLED
        if COPTIC_ENABLED:
            texts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts', 'cop')
            if os.path.isdir(texts_dir):
                languages.append({'code': 'cop', 'label': 'Coptic'})
                crosslingual_pairs.extend([
                    {'key': 'cop-grc', 'source': 'cop', 'target': 'grc', 'label': 'Coptic → Greek'},
                ])
    except ImportError:
        pass
    try:
        from backend.hebrew import HEBREW_ENABLED
        if HEBREW_ENABLED:
            texts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts', 'he')
            if os.path.isdir(texts_dir):
                languages.append({'code': 'he', 'label': 'Hebrew'})
                crosslingual_pairs.extend([
                    {'key': 'he-grc', 'source': 'he', 'target': 'grc', 'label': 'Hebrew → Greek'},
                    {'key': 'he-la', 'source': 'he', 'target': 'la', 'label': 'Hebrew → Latin'},
                ])
    except ImportError:
        pass
    # Persian/Urdu/Arabic (2026-09-05): the three share a script and much
    # vocabulary, so their cross-language pairs work through a shared
    # comparison form (backend/perso_arabic.py) rather than a dictionary CSV.
    # The pairs are appended below once the languages are known to be present.
    try:
        from backend.persian import PERSIAN_ENABLED
        if PERSIAN_ENABLED:
            texts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts', 'fa')
            if os.path.isdir(texts_dir):
                languages.append({'code': 'fa', 'label': 'Persian'})
    except ImportError:
        pass
    try:
        from backend.urdu import URDU_ENABLED
        if URDU_ENABLED:
            texts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts', 'ur')
            if os.path.isdir(texts_dir):
                languages.append({'code': 'ur', 'label': 'Urdu'})
    except ImportError:
        pass
    try:
        from backend.arabic import ARABIC_ENABLED
        if ARABIC_ENABLED:
            texts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts', 'ar')
            if os.path.isdir(texts_dir):
                languages.append({'code': 'ar', 'label': 'Arabic'})
    except ImportError:
        pass
    present = {l['code'] for l in languages}
    for src, tgt, label in (('fa', 'ur', 'Persian → Urdu'),
                            ('ar', 'fa', 'Arabic → Persian'),
                            ('ar', 'ur', 'Arabic → Urdu')):
        if src in present and tgt in present:
            crosslingual_pairs.append({'key': f'{src}-{tgt}', 'source': src, 'target': tgt, 'label': label})
    allowed = _allowed_languages()
    if allowed:
        order = [x.strip() for x in os.environ.get('TESSERAE_LANGUAGES', '').split(',') if x.strip()]
        languages = sorted((l for l in languages if l['code'] in allowed),
                           key=lambda l: order.index(l['code']))   # the allow-list's order is the tab order
        crosslingual_pairs = [p for p in crosslingual_pairs
                              if p['source'] in allowed and p['target'] in allowed]

    # Documents collection (stage 3b-2), behind TESSERAE_DOCUMENTS=1: the
    # client reads this to decide whether to offer the Literature/Documents/
    # Both control on the corpus-wide phrase search at all. True only when
    # the switch is on AND at least one language actually has a built
    # documents index -- never advertised as available with nothing to search.
    documents_enabled = False
    try:
        import backend.documents as _docs_mod
        documents_enabled = _docs_mod.enabled() and any(
            _docs_mod.is_index_available(lang) for lang in _docs_mod.SUPPORTED_LANGUAGES)
    except ImportError:
        pass
    crosslingual_pairs = [p for p in crosslingual_pairs if p['key'] not in CROSSLINGUAL_HELD]
    return jsonify({'languages': languages, 'crosslingual_pairs': crosslingual_pairs,
                    'crosslingual_held': held, 'documents_enabled': documents_enabled})


# =============================================================================
# TEXT AND CORPUS API ROUTES
# =============================================================================

@api_route('/check-meter')
def check_meter():
    """Check if source and target texts are suitable for metrical analysis (both poetry)"""
    source = request.args.get('source', '')
    target = request.args.get('target', '')
    language = request.args.get('language', 'la')
    
    if language == 'en':
        return jsonify({'available': False, 'reason': 'Metrical analysis not available for English'})
    
    try:
        from backend.metrical_scanner import is_suitable_for_meter
    except ImportError:
        from metrical_scanner import is_suitable_for_meter
    
    available = is_suitable_for_meter(source, target, language)
    
    if not available:
        return jsonify({'available': False, 'reason': 'One or both texts appear to be prose'})
    
    return jsonify({'available': True})


@api_route('/author-dates')
def get_public_author_dates():
    """Get author dates for timeline visualization (public endpoint)"""
    return jsonify(AUTHOR_DATES)


@api_route('/cache/stats')
def cache_stats():
    return jsonify(get_cache_stats())


@api_route('/stats')
def get_stats():
    stats = {
        'languages': {},
        'total_texts': 0
    }
    
    for lang in ['la', 'grc', 'en']:
        lang_dir = os.path.join(TEXTS_DIR, lang)
        if os.path.exists(lang_dir):
            count = len([f for f in os.listdir(lang_dir) if f.endswith('.tess')])
            stats['languages'][lang] = count
            stats['total_texts'] += count
    
    cache = get_cache_stats()
    stats['cache'] = cache
    
    return jsonify(stats)
