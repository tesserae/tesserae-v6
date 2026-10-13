"""
Tesserae V6 - Flask API Server

Main application entry point for the Tesserae V6 intertextual analysis platform.
Provides REST API endpoints for text search, corpus management, and user features.

See docs/API.md for endpoint documentation.
See docs/DEVELOPER.md for setup and architecture details.
"""
# =============================================================================
# IMPORTS
# =============================================================================
from flask import Flask, send_from_directory, jsonify, request, session
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

import os

# The shared objects live in backend/runtime.py; they are imported here under
# the names this module has always exported (tests, scripts and the .wsgi use them).
from backend.models import db  # noqa: F401
from backend.runtime import (  # noqa: F401
    logger, app_logger, natural_sort_key, get_db_cursor,
    DIST_FOLDER, LEGACY_FRONTEND, STATIC_FOLDER, DEPLOYMENT_ENV, DIRECT_SERVER, API_PREFIX,
    text_processor, matcher, scorer, TEXTS_DIR, processed_cache, get_processed_units,
    ADMIN_PASSWORD, AUTHOR_DATES, init_db,
    ensure_caches_ready, start_cache_init, _initialize_caches_background,
)
from backend.frequency_cache import get_corpus_frequencies


# =============================================================================
# HOOKS AND STATIC ROUTES (registered by create_app, in the order below)
# =============================================================================
def add_security_headers(response):
    """Add standard HTTP security headers to all API responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    # Only send HSTS outside of local dev to avoid sticky local browser issues
    if DEPLOYMENT_ENV != 'dev':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


def _cache_headers(response):
    path = request.path or ''
    if path.startswith('/assets/') and '-' in path.rsplit('/', 1)[-1]:
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    elif path == '/' or path.endswith('.html') or 'text/html' in (
            response.headers.get('Content-Type') or ''):
        response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    return response


def make_session_permanent():
    """Keep user sessions alive across browser restarts"""
    session.permanent = True


def add_header(response):
    """Disable browser caching to ensure fresh content"""
    if request.endpoint == 'objects.object_image' and response.status_code == 200:
        return response  # a museum picture from our cache keeps its own 30-day Cache-Control
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


def index():
    static_folder = app.static_folder or '../frontend'
    return send_from_directory(static_folder, 'index.html')


def serve_static_downloads():
    """Intercept /static/downloads/ before Flask's built-in static handler.

    Flask's static handler (with static_url_path='') tries to serve ALL paths
    from dist/, fails for /static/downloads/*, and triggers the 404 catch-all
    which returns index.html. This before_request hook catches download paths
    first and serves them from the actual static/downloads/ directory.
    """
    if request.path.startswith('/static/downloads/'):
        filepath = request.path[len('/static/downloads/'):]
        downloads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'downloads')
        try:
            return send_from_directory(downloads_dir, filepath)
        except Exception:
            return jsonify({'error': 'File not found'}), 404


def legacy_frontend():
    """Serve the legacy frontend for full feature access during migration"""
    legacy_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
    return send_from_directory(legacy_path, 'index.html')


def page_not_found(e):
    """Handle 404 errors by serving the SPA for client-side routing.

    Unknown API routes must return a JSON 404, not the SPA HTML — otherwise an
    AI agent (or any client) hitting a wrong/renamed endpoint silently gets a
    200 page of HTML and can't tell it failed. On production Apache mounts Flask
    at /api (WSGIScriptAlias /api), so an unknown /api/... call reaches Flask
    with the /api stripped (e.g. /bogus) and script_root == '/api'; treat any
    such request as an API request too. Genuine SPA client routes (/help,
    /about, …) are served by Apache from the static build and never reach Flask
    on prod; in the dev direct-server they arrive without the /api prefix and
    still fall through to index.html below."""
    api_path = f"{API_PREFIX}/" if API_PREFIX else "/api/"
    script_root = (request.script_root or '').rstrip('/')
    is_api_request = request.path.startswith(api_path) or script_root.endswith('/api')
    if is_api_request:
        return jsonify({'error': 'Not found', 'path': request.path,
                        'hint': 'Check the endpoint path against /api/texts and the API guide; '
                                'all API paths are under /api/.'}), 404
    # Don't serve SPA for static file requests — return real 404
    if request.path.startswith('/static/'):
        return jsonify({'error': 'File not found'}), 404
    static_folder = app.static_folder or '../frontend'
    return send_from_directory(static_folder, 'index.html')


def api_route(path, **kwargs):
    """Decorator for API routes that auto-prepends API_PREFIX.
    On Marvin (behind Apache), prefix is empty. On dev, prefix is /api."""
    full_path = f"{API_PREFIX}{path}" if path != "/" else API_PREFIX or "/"
    return app.route(full_path, **kwargs)


def create_app():
    """Build the Flask application, register every blueprint, return it.

    The steps run in the order they ran when this module built the application
    at import: the same hooks in the same order, the same blueprints with the
    same prefixes. backend/app.py calls it once, at the bottom, so that
    `from backend.app import app` keeps working.
    """
    # Create Flask app with static file serving
    app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path='')

    # Secure CORS: Restrict to allowed origins instead of wildcard, defaulting to localhost and production domains
    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.environ.get(
            "TESSERAE_ALLOWED_ORIGINS",
            "http://localhost:5173,http://localhost:5000,https://tesserae.caset.buffalo.edu,http://tesserae.caset.buffalo.edu"
        ).split(",")
        if origin.strip()
    ]
    CORS(app, supports_credentials=True, origins=ALLOWED_ORIGINS)

    app.after_request(add_security_headers)

    # Application configuration
    _session_secret = os.environ.get("SESSION_SECRET")
    if _session_secret:
        app.secret_key = _session_secret
    elif os.environ.get("DEPLOYMENT_ENV", "production") == "dev":
        app_logger.warning("SESSION_SECRET not set; generating ephemeral dev secret key")
        app.secret_key = os.urandom(32).hex()
    else:
        raise RuntimeError("SESSION_SECRET environment variable must be set in non-dev environments")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # Handle proxy headers

    app.after_request(_cache_headers)
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching for development
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {'pool_pre_ping': True, "pool_recycle": 300}

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )
    if DEPLOYMENT_ENV != 'dev':
        app.config['SESSION_COOKIE_SECURE'] = True

    # =============================================================================
    # DATABASE INITIALIZATION
    # =============================================================================
    db.init_app(app)

    # Create all database tables defined in models.py
    # Wrapped in try/except to allow server to start even if DB is temporarily unavailable
    try:
        with app.app_context():
            db.create_all()
        app_logger.info("Database tables initialized successfully")
    except Exception as e:
        app_logger.warning(f"Could not initialize database tables: {e}")
        app_logger.warning("Database will be initialized on first request")

    # =========================================================================
    # AUTHENTICATION SETUP
    # =========================================================================
    from backend.marvin_auth import init_marvin_auth
    init_marvin_auth(app)

    init_db()

    from backend.blueprints import (
        admin_bp, init_admin_blueprint,
        search_bp, init_search_blueprint,
        corpus_bp, init_corpus_blueprint
    )
    from backend.blueprints.intertext import intertext_bp
    from backend.blueprints.downloads import downloads_bp
    from backend.blueprints.usage import usage_bp
    from backend.blueprints.job_uploads import job_uploads_bp
    from backend.blueprints.hapax import hapax_bp, init_hapax_blueprint
    from backend.blueprints.batch import batch_bp, init_batch_blueprint
    from backend.blueprints.api_docs import api_docs_bp
    from backend.blueprints.fusion import fusion_bp, init_fusion_blueprint
    from backend.blueprints.mcp_http import mcp_http_bp
    from backend.blueprints.mcp_oauth import mcp_oauth_bp
    from backend.blueprints.feature_request import feature_request_bp
    from backend.blueprints.passages import passages_bp
    from backend.blueprints.assistant import assistant_bp
    from backend.blueprints.reuse import reuse_bp
    from backend.blueprints.auth import auth_bp
    from backend.blueprints.meta import meta_bp
    from backend.blueprints.text import text_bp
    from backend.blueprints.documents import documents_bp
    from backend.blueprints.line_search import line_search_bp
    from backend.blueprints.feedback import feedback_bp
    from backend.blueprints.features import features_bp

    author_dates_path = os.path.join(os.path.dirname(__file__), 'author_dates.json')

    init_admin_blueprint(
        admin_password=ADMIN_PASSWORD,
        author_dates=AUTHOR_DATES,
        author_dates_path=author_dates_path,
        text_processor=text_processor,
        texts_dir=TEXTS_DIR,
        processed_cache_ref=processed_cache
    )

    init_search_blueprint(
        matcher=matcher,
        scorer=scorer,
        text_processor=text_processor,
        texts_dir=TEXTS_DIR,
        get_processed_units_fn=get_processed_units,
        get_corpus_frequencies_fn=get_corpus_frequencies
    )

    init_corpus_blueprint(
        texts_dir=TEXTS_DIR,
        text_processor=text_processor,
        get_processed_units_fn=get_processed_units
    )

    init_hapax_blueprint(
        texts_dir=TEXTS_DIR,
        text_processor=text_processor,
        author_dates=AUTHOR_DATES
    )

    init_batch_blueprint(
        matcher=matcher,
        scorer=scorer,
        texts_dir=TEXTS_DIR,
        get_processed_units_fn=get_processed_units,
        admin_password=ADMIN_PASSWORD,
        text_processor=text_processor,
        get_corpus_frequencies_fn=get_corpus_frequencies,
        author_dates=AUTHOR_DATES
    )

    init_fusion_blueprint(
        matcher=matcher,
        scorer=scorer,
        text_processor=text_processor,
        texts_dir=TEXTS_DIR,
        get_processed_units_fn=get_processed_units,
    )

    # Register blueprints with environment-aware prefix.
    # On Marvin: API_PREFIX="" (Apache strips /api via WSGIScriptAlias)
    # On dev: API_PREFIX="/api" (Flask handles the full URL)
    admin_prefix = f"{API_PREFIX}/admin" if API_PREFIX else "/admin"
    intertext_prefix = f"{API_PREFIX}/intertexts" if API_PREFIX else None  # None = use blueprint's own /intertexts
    batch_prefix = f"{API_PREFIX}/batch" if API_PREFIX else None  # None = use blueprint's own /batch

    app.register_blueprint(admin_bp, url_prefix=admin_prefix)
    app.register_blueprint(search_bp, url_prefix=API_PREFIX or None)
    app.register_blueprint(corpus_bp, url_prefix=API_PREFIX or None)
    app.register_blueprint(intertext_bp, url_prefix=intertext_prefix)
    app.register_blueprint(usage_bp, url_prefix=API_PREFIX or None)
    app.register_blueprint(downloads_bp, url_prefix=API_PREFIX or None)
    app.register_blueprint(job_uploads_bp, url_prefix=API_PREFIX or None)
    app.register_blueprint(hapax_bp, url_prefix=API_PREFIX or None)
    app.register_blueprint(batch_bp, url_prefix=batch_prefix)
    app.register_blueprint(api_docs_bp, url_prefix=API_PREFIX or None)
    app.register_blueprint(passages_bp, url_prefix=API_PREFIX or None)
    app.register_blueprint(assistant_bp, url_prefix=API_PREFIX or None)
    app.register_blueprint(fusion_bp, url_prefix=API_PREFIX or None)
    app.register_blueprint(mcp_http_bp, url_prefix=API_PREFIX or None)
    app.register_blueprint(mcp_oauth_bp, url_prefix=API_PREFIX or None)
    app.register_blueprint(feature_request_bp, url_prefix=API_PREFIX or None)
    app.register_blueprint(reuse_bp, url_prefix=API_PREFIX or None)
    from backend.blueprints.scholarship import scholarship_bp  # noqa: E402
    app.register_blueprint(scholarship_bp, url_prefix=API_PREFIX or None)
    from backend.blueprints.events import events_bp  # noqa: E402
    app.register_blueprint(events_bp, url_prefix=API_PREFIX or None)
    from backend.blueprints.coins import coins_bp  # noqa: E402
    app.register_blueprint(coins_bp, url_prefix=API_PREFIX or None)
    from backend.blueprints.objects import objects_bp  # noqa: E402
    app.register_blueprint(objects_bp, url_prefix=API_PREFIX or None)
    from backend.blueprints.scope import scope_bp  # noqa: E402
    app.register_blueprint(scope_bp, url_prefix=API_PREFIX or None)

    app_logger.info(f"Blueprints registered (API_PREFIX='{API_PREFIX}', env={DEPLOYMENT_ENV})")

    # =============================================================================
    # PLUGIN LANGUAGES (Coptic, Hebrew, Persian, Urdu, Arabic)
    # =============================================================================
    try:
        from backend.coptic import register as register_coptic
        register_coptic()
    except ImportError:
        pass

    try:
        from backend.hebrew import register as register_hebrew
        register_hebrew()
    except ImportError:
        pass

    # Persian, Urdu and Arabic are DEVELOPMENT languages (ported from the demo
    # branch in October 2026): their modules live in the repository but register
    # only when TESSERAE_LANGUAGES names them. Production leaves the variable
    # unset and so never serves them until the maintainer opens them.
    try:
        from backend.served_languages import allowed_languages as _served_allowed
        _opted_in = _served_allowed() or set()
        if 'fa' in _opted_in:
            from backend.persian import register as register_persian
            register_persian()
        if 'ur' in _opted_in:
            from backend.urdu import register as register_urdu
            register_urdu()
        if 'ar' in _opted_in:
            from backend.arabic import register as register_arabic
            register_arabic()
    except ImportError:
        pass

    # =========================================================================
    # REQUEST MIDDLEWARE
    # =========================================================================
    # These run before/after every request to handle sessions and caching
    app.before_request(make_session_permanent)
    app.after_request(add_header)

    # Static file routes
    app.add_url_rule('/', view_func=index)
    app.before_request(serve_static_downloads)
    app.add_url_rule('/legacy', view_func=legacy_frontend)
    app.register_error_handler(404, page_not_found)

    # Routes that used to be defined here with api_route(); each blueprint
    # builds the same prefixed paths itself (see api_route_for in backend/runtime.py).
    for blueprint in (auth_bp, meta_bp, text_bp, documents_bp, line_search_bp, feedback_bp, features_bp):
        app.register_blueprint(blueprint)

    return app


# Create Flask app with static file serving
app = create_app()

# Names that other modules, scripts and tests take from backend.app.
from backend.line_search_support import _normalize_lemma, _normalize_latin_lemma  # noqa: E402,F401
from backend.blueprints.line_search import (  # noqa: E402,F401
    _hebrew_unpointed_fallbacks, _line_lemmas_matching_query, _univerbation_lemmatize,
    _surface_hits, _is_near_quotation, _span, _dedup_same_passage, rare_focus_filter,
)
from backend.blueprints.documents import (  # noqa: E402,F401
    _document_passes_filters, DOCUMENTS_FORMULA_DEFAULT_N, _restoration_flags,
    _find_exact_phrase_positions, _normalize_token_for_phrase_match,
)


if __name__ == "__main__":
    app_logger.info("Starting Tesserae V6 development server...")
    debug_mode = os.environ.get("TESSERAE_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)  # nosec B104
