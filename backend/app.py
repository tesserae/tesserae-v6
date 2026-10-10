"""
Tesserae V6 - Flask API Server

Main application entry point for the Tesserae V6 intertextual analysis platform.
Provides REST API endpoints for text search, corpus management, and user features.

Key Components:
    - Text Search: Parallel phrase matching between source/target texts
    - Line Search: Single-line search across the entire corpus
    - Hapax Search: Find rare words shared between texts
    - Corpus Browser: Text listing and metadata retrieval
    - Intertext Repository: Save and share discovered parallels
    - Admin Panel: Manage text requests, cache, and settings

Technical Features:
    - Result caching for repeated searches
    - Zipf-based automatic stoplist generation
    - V3-style scoring with IDF and distance metrics
    - CLTK/NLTK lemmatization for Latin, Greek, and English
    - Pre-built inverted index for fast corpus-wide searches

See docs/API.md for endpoint documentation.
See docs/DEVELOPER.md for setup and architecture details.
"""
# =============================================================================
# IMPORTS
# =============================================================================
# Flask and web framework dependencies
from flask import Flask, send_from_directory, jsonify, request, session
from flask_cors import CORS
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

# Standard library
import os
import json
import re
import math
import itertools
import threading
from datetime import datetime

# Application modules
from backend.logging_config import setup_logging, get_logger
from backend.db_utils import get_db_cursor
from backend.services import get_user_location, log_search

# =============================================================================
# LOGGING SETUP
# =============================================================================
logger = setup_logging()
app_logger = get_logger('app')


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================
def natural_sort_key(s):
    """Sort strings with embedded numbers in natural order (1, 2, 10 not 1, 10, 2)"""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(s))]

from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.utils import get_text_metadata, clean_cts_reference, resolve_text_path, exact_phrase_pattern, strip_hebrew_pointing, exact_search_text, format_short_locus
from backend.cache import get_cache_stats
from backend.frequency_cache import get_corpus_frequencies, initialize_all_caches
from backend.bigram_frequency import initialize_bigram_caches
from backend.distance_filter import passes_distance_filter, is_prose_text as is_prose_text_unified
from backend.lemma_cache import get_cached_units, save_cached_units, get_file_hash
from backend.feature_extractor import feature_extractor

# =============================================================================
# FLASK APPLICATION INITIALIZATION
# =============================================================================
# Determine which frontend to serve (React build or legacy)
DIST_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dist')
LEGACY_FRONTEND = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
STATIC_FOLDER = DIST_FOLDER if os.path.exists(DIST_FOLDER) else LEGACY_FRONTEND

# API prefix handling:
# - Behind Apache (production): WSGIScriptAlias /api strips the prefix, so Flask
#   routes don't need it. API_PREFIX = ""
# - Direct Flask server (dev): Flask gets the full /api/... URL from the browser,
#   so routes need the /api prefix. API_PREFIX = "/api"
# main.py sets TESSERAE_DIRECT_SERVER=1 when running Flask directly.
DEPLOYMENT_ENV = os.environ.get("DEPLOYMENT_ENV", "dev")
DIRECT_SERVER = os.environ.get("TESSERAE_DIRECT_SERVER", "") == "1"
API_PREFIX = "/api" if DIRECT_SERVER else ""
if DEPLOYMENT_ENV == 'marvin' and not DIRECT_SERVER:
    app_logger.warning("DEPLOYMENT_ENV=marvin but TESSERAE_DIRECT_SERVER not set.")
    app_logger.warning("  If running Flask directly (not behind Apache), set TESSERAE_DIRECT_SERVER=1")

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

@app.after_request
def add_security_headers(response):
    """Add standard HTTP security headers to all API responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    # Only send HSTS outside of local dev to avoid sticky local browser issues
    if DEPLOYMENT_ENV != 'dev':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

def api_route(path, **kwargs):
    """Decorator for API routes that auto-prepends API_PREFIX.
    On Marvin (behind Apache), prefix is empty. On dev, prefix is /api."""
    full_path = f"{API_PREFIX}{path}" if path != "/" else API_PREFIX or "/"
    return app.route(full_path, **kwargs)


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


@app.after_request
def _cache_headers(response):
    path = request.path or ''
    if path.startswith('/assets/') and '-' in path.rsplit('/', 1)[-1]:
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    elif path == '/' or path.endswith('.html') or 'text/html' in (
            response.headers.get('Content-Type') or ''):
        response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    return response
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
from backend.models import db
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

# =============================================================================
# AUTHENTICATION SETUP
# =============================================================================
from backend.marvin_auth import (
    init_marvin_auth,
    get_current_user_info,
    update_user_orcid,
    unlink_user_orcid,
)
init_marvin_auth(app)

# =============================================================================
# CORE PROCESSING COMPONENTS
# =============================================================================
# These are the main engines for text analysis:
# - TextProcessor: Handles tokenization, lemmatization, and text parsing
# - Matcher: Finds parallel passages between source and target texts
# - Scorer: Calculates similarity scores using V3-style algorithm
text_processor = TextProcessor()
matcher = Matcher()
scorer = Scorer()

# Path to the corpus of .tess text files (organized by language)
TEXTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')

# In-memory cache for processed text units (reduces reprocessing)
processed_cache = {}


def get_processed_units(text_id, language, unit_type, text_processor):
    """Get processed units, using file-based lemma cache when available"""
    filepath = resolve_text_path(TEXTS_DIR, language, text_id)
    if not filepath:
        raise FileNotFoundError(f"Text file not found: {text_id}")

    # Use the resolved basename as the canonical cache identity so that
    # NFC vs NFD variants of the same filename always hit the same entry
    resolved_id = os.path.basename(filepath)
    cache_key = f"{filepath}:{language}:{unit_type}"

    if cache_key in processed_cache:
        return processed_cache[cache_key]

    cached = get_cached_units(resolved_id, language)
    if cached:
        units_key = 'units_phrase' if unit_type == 'phrase' else 'units_line'
        if units_key in cached:
            units = cached[units_key]
            processed_cache[cache_key] = units
            return units

    units = text_processor.process_file(filepath, language, unit_type)
    processed_cache[cache_key] = units

    try:
        file_hash = get_file_hash(filepath)
        units_line = units if unit_type == 'line' else text_processor.process_file(filepath, language, 'line')
        units_phrase = units if unit_type == 'phrase' else text_processor.process_file(filepath, language, 'phrase')
        save_cached_units(resolved_id, language, units_line, units_phrase, file_hash)
    except Exception:
        app_logger.exception(f"Failed to save cached units for {resolved_id}")

    return units


# =============================================================================
# CONFIGURATION AND CONSTANTS
# =============================================================================
# Admin password for protected operations (text approval, cache management)
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')

# Author dates for timeline visualization (loaded from JSON file)
AUTHOR_DATES = {}
author_dates_path = os.path.join(os.path.dirname(__file__), 'author_dates.json')
if os.path.exists(author_dates_path):
    with open(author_dates_path, 'r', encoding='utf-8') as f:
        AUTHOR_DATES = json.load(f)


# =============================================================================
# DATABASE TABLE CREATION
# =============================================================================
def init_db():
    """Initialize the database tables"""
    try:
        with get_db_cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS text_requests (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    author VARCHAR(255) NOT NULL,
                    work VARCHAR(255) NOT NULL,
                    language VARCHAR(10) DEFAULT 'la',
                    notes TEXT,
                    content TEXT,
                    status VARCHAR(50) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    reviewed_by VARCHAR(255),
                    admin_notes TEXT,
                    text_date TEXT,
                    approved_filename VARCHAR(255),
                    official_author VARCHAR(255),
                    official_work VARCHAR(255),
                    admin_updated_at TIMESTAMP,
                    author_era VARCHAR(100),
                    author_year INTEGER,
                    e_source VARCHAR(255),
                    e_source_url TEXT,
                    print_source TEXT,
                    added_by VARCHAR(255)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255),
                    email VARCHAR(255),
                    feedback_type VARCHAR(50) DEFAULT 'suggestion',
                    message TEXT NOT NULL,
                    status VARCHAR(50) DEFAULT 'new',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    admin_notes TEXT,
                    responded_by VARCHAR(255),
                    responded_at TIMESTAMP
                )
            ''')
            cur.execute('''
                ALTER TABLE feedback ADD COLUMN IF NOT EXISTS responded_by VARCHAR(255)
            ''')
            cur.execute('''
                ALTER TABLE feedback ADD COLUMN IF NOT EXISTS responded_at TIMESTAMP
            ''')
            # Migration for users table to track session versions (Issue #86)
            cur.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER DEFAULT 1')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key VARCHAR(255) PRIMARY KEY,
                    value TEXT
                )
            ''')
            # Create/Update table schema
            cur.execute('''
                CREATE TABLE IF NOT EXISTS search_logs (
                    id SERIAL PRIMARY KEY,
                    search_type VARCHAR(50) NOT NULL,
                    language VARCHAR(10) DEFAULT 'la',
                    source_text VARCHAR(255),
                    target_text VARCHAR(255),
                    query_text TEXT,
                    match_type VARCHAR(50),
                    results_count INTEGER DEFAULT 0,
                    cached BOOLEAN DEFAULT FALSE,
                    user_id VARCHAR(255),
                    client_ip VARCHAR(50),
                    city VARCHAR(100),
                    country VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cur.execute('ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS client_ip VARCHAR(50)')
            cur.execute('ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS city VARCHAR(100)')
            cur.execute('ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS country VARCHAR(100)')

            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_search_logs_created_at ON search_logs(created_at)
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_search_logs_language ON search_logs(language)
            ''')
            # First-party page views: which pages each visit opened, in order.
            cur.execute('''
                CREATE TABLE IF NOT EXISTS page_views (
                    id SERIAL PRIMARY KEY,
                    visit_id VARCHAR(32) NOT NULL,
                    path VARCHAR(300),
                    page VARCHAR(60),
                    language VARCHAR(8),
                    referrer_host VARCHAR(200),
                    client_ip VARCHAR(64),
                    city VARCHAR(120),
                    country VARCHAR(120),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_page_views_visit ON page_views(visit_id, created_at)')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_page_views_created ON page_views(created_at)')
            cur.execute('''
                ALTER TABLE users ADD COLUMN IF NOT EXISTS must_reset_password BOOLEAN DEFAULT FALSE
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS roles (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(50) UNIQUE NOT NULL,
                    description TEXT
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id VARCHAR(255) NOT NULL,
                    role_id INTEGER NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    assigned_by VARCHAR(255),
                    PRIMARY KEY (user_id, role_id)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS admin_audit_log (
                    id SERIAL PRIMARY KEY,
                    admin_username VARCHAR(255),
                    action VARCHAR(255) NOT NULL,
                    target_type VARCHAR(100),
                    target_id VARCHAR(255),
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cur.execute('''
                INSERT INTO roles (name, description)
                VALUES ('USER', 'Standard user')
                ON CONFLICT (name) DO NOTHING
            ''')
            cur.execute('''
                INSERT INTO roles (name, description)
                VALUES ('ADMIN', 'Administrator')
                ON CONFLICT (name) DO NOTHING
            ''')
            cur.execute('''
                INSERT INTO roles (name, description)
                VALUES ('SUPER_ADMIN', 'Super administrator')
                ON CONFLICT (name) DO NOTHING
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS dictionary_review (
                    id SERIAL PRIMARY KEY,
                    greek_lemma VARCHAR(255) NOT NULL,
                    latin_lemma VARCHAR(255) NOT NULL,
                    shared_senses TEXT,
                    score REAL DEFAULT 0,
                    source VARCHAR(100) DEFAULT 'perseus_pivot',
                    greek_pos VARCHAR(50),
                    latin_pos VARCHAR(50),
                    status VARCHAR(20) DEFAULT 'pending',
                    reviewed_by VARCHAR(255),
                    reviewed_at TIMESTAMP,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_dict_review_status ON dictionary_review(status)
            ''')
            cur.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_dict_review_pair
                ON dictionary_review(greek_lemma, latin_lemma, source)
            ''')
        app_logger.info("Database initialized successfully")
    except Exception as e:
        app_logger.error(f"Database initialization error: {e}")

init_db()


# =============================================================================
# FREQUENCY CACHE INITIALIZATION (DEFERRED)
# =============================================================================
# Pre-compute word and bigram frequencies for stoplist generation and scoring
# NOTE: Initialization is deferred to background thread to allow server to start
# quickly and pass health checks in production
import threading

_caches_initialized = False
_caches_initializing = False
_cache_init_lock = threading.Lock()

def _initialize_caches_background():
    """Initialize frequency caches in background thread"""
    global _caches_initialized, _caches_initializing
    with _cache_init_lock:
        if _caches_initialized or _caches_initializing:
            return
        _caches_initializing = True
    
    try:
        app_logger.info("Initializing corpus frequency caches (background)...")
        initialize_all_caches(text_processor)
        initialize_bigram_caches(text_processor)
        app_logger.info("Frequency caches ready.")
        _caches_initialized = True
    except Exception as e:
        app_logger.error(f"Error initializing caches: {e}")
    finally:
        _caches_initializing = False

def ensure_caches_ready():
    """Ensure caches are initialized (called before searches)"""
    global _caches_initialized
    if not _caches_initialized:
        _initialize_caches_background()
    return _caches_initialized

# Start background cache initialization after server starts
def start_cache_init():
    thread = threading.Thread(target=_initialize_caches_background, daemon=True)
    thread.start()


# =============================================================================
# BLUEPRINT REGISTRATION
# =============================================================================
# Flask blueprints organize related routes into separate modules:
# - admin_bp: Admin panel for text management and settings
# - search_bp: Main search functionality (parallel matching)
# - corpus_bp: Corpus browsing and text listing
# - intertext_bp: Repository for saving/sharing discovered parallels
# - downloads_bp: Export functionality (CSV, etc.)
# - hapax_bp: Rare word and rare pair searches
# - batch_bp: Batch processing for multiple searches
# - api_docs_bp: API documentation
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
from backend.email_notifications import notify_text_request, notify_feedback

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


# =============================================================================
# REQUEST MIDDLEWARE
# =============================================================================
# These run before/after every request to handle sessions and caching

@app.before_request
def make_session_permanent():
    """Keep user sessions alive across browser restarts"""
    session.permanent = True


@app.after_request
def add_header(response):
    """Disable browser caching to ensure fresh content"""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# =============================================================================
# STATIC FILE ROUTES
# =============================================================================

@app.route('/')
def index():
    static_folder = app.static_folder or '../frontend'
    return send_from_directory(static_folder, 'index.html')

@app.before_request
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

@app.route('/legacy')
def legacy_frontend():
    """Serve the legacy frontend for full feature access during migration"""
    legacy_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
    return send_from_directory(legacy_path, 'index.html')

@app.errorhandler(404)
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


# =============================================================================
# AUTHENTICATION API ROUTES
# =============================================================================

@api_route('/auth/user')
def get_auth_user():
    """Get current logged-in user info"""
    user_info = get_current_user_info()
    auth_type = 'password'
    self_registration_enabled = os.environ.get('DISABLE_SELF_REGISTER', 'false').lower() not in ('true', '1', 'yes')
    return jsonify({
        'user': user_info,
        'auth_enabled': True,
        'auth_type': auth_type,
        'self_registration_enabled': self_registration_enabled,
    })

@api_route('/auth/saved-searches')
def get_saved_searches():
    """Get saved searches for current user"""
    if not current_user.is_authenticated:
        return jsonify([])
    from backend.models import SavedSearch
    searches = SavedSearch.query.filter_by(user_id=current_user.id).order_by(SavedSearch.created_at.desc()).all()
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'language': s.language,
        'source_author': s.source_author,
        'source_work': s.source_work,
        'source_section': s.source_section,
        'target_author': s.target_author,
        'target_work': s.target_work,
        'target_section': s.target_section,
        'match_type': s.match_type,
        'min_matches': s.min_matches,
        'stoplist_basis': s.stoplist_basis,
        'stoplist_size': s.stoplist_size,
        'max_distance': s.max_distance,
        'source_unit_type': s.source_unit_type,
        'target_unit_type': s.target_unit_type,
    } for s in searches])

@api_route('/auth/saved-searches', methods=['POST'])
def save_search():
    """Save a search configuration for current user"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not logged in'}), 401
    from backend.models import SavedSearch
    data = request.json
    search = SavedSearch(
        user_id=current_user.id,
        name=data.get('name', 'Untitled Search'),
        language=data.get('language', 'la'),
        source_author=data.get('source_author'),
        source_work=data.get('source_work'),
        source_section=data.get('source_section'),
        target_author=data.get('target_author'),
        target_work=data.get('target_work'),
        target_section=data.get('target_section'),
        match_type=data.get('match_type', 'lemma'),
        min_matches=data.get('min_matches', 2),
        stoplist_basis=data.get('stoplist_basis', 'corpus'),
        stoplist_size=data.get('stoplist_size', 10),
        max_distance=data.get('max_distance', 10),
        source_unit_type=data.get('source_unit_type', 'line'),
        target_unit_type=data.get('target_unit_type', 'line'),
    )
    db.session.add(search)
    db.session.commit()
    return jsonify({'success': True, 'id': search.id})

@api_route('/auth/saved-searches/<int:search_id>', methods=['DELETE'])
def delete_saved_search(search_id):
    """Delete a saved search"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not logged in'}), 401
    from backend.models import SavedSearch
    search = SavedSearch.query.filter_by(id=search_id, user_id=current_user.id).first()
    if not search:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(search)
    db.session.commit()
    return jsonify({'success': True})

@api_route('/auth/profile', methods=['PUT'])
def update_profile():
    """Update user profile (institution)"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.json
    current_user.institution = data.get('institution', current_user.institution)
    db.session.commit()
    return jsonify({'success': True, 'user': get_current_user_info()})

@api_route('/auth/orcid/link', methods=['POST'])
def link_orcid():
    """Link an ORCID to user account (manual entry for now)"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.json
    orcid = data.get('orcid', '').strip()
    orcid_name = data.get('orcid_name', '').strip()
    if not orcid:
        return jsonify({'error': 'ORCID is required'}), 400
    orcid_pattern = re.compile(r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$')
    if not orcid_pattern.match(orcid):
        return jsonify({'error': 'Invalid ORCID format. Expected: 0000-0000-0000-0000'}), 400
    if update_user_orcid(current_user.id, orcid, orcid_name):
        return jsonify({'success': True, 'user': get_current_user_info()})
    return jsonify({'error': 'Failed to update ORCID'}), 500

@api_route('/auth/orcid/unlink', methods=['POST'])
def unlink_orcid():
    """Remove ORCID from user account"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not logged in'}), 401
    if unlink_user_orcid(current_user.id):
        return jsonify({'success': True, 'user': get_current_user_info()})
    return jsonify({'error': 'Failed to unlink ORCID'}), 500

# =============================================================================
# HEALTH CHECK ROUTES
# =============================================================================

@app.route('/health')
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
    return jsonify({'languages': languages, 'crosslingual_pairs': crosslingual_pairs,
                    'documents_enabled': documents_enabled})


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


# =============================================================================
# PROSE DETECTION HELPERS
# =============================================================================
# Prose detection delegated to unified detect_text_type() in utils.py via
# distance_filter.is_prose_text (imported as is_prose_text_unified at top).
# POETRY_MAX_DISTANCE / PROSE_MAX_DISTANCE kept here for app.py's own use.

POETRY_MAX_DISTANCE = 20
PROSE_MAX_DISTANCE = 4


# One shared rule, backend/latin_orthography.py. This used to keep case,
# which a lemma from the tables never has.
from backend.latin_orthography import fold_latin as _normalize_latin_lemma  # noqa: E402


def _hebrew_unpointed_fallbacks(query, query_lemmas, stopwords):
    """For a Hebrew query, the index fallback forms that let a word typed
    without vowel points match every homograph reading of its consonants.
    Returns (fallback_forms or None, query_lemmas), where a lemma the
    stoplist would drop is replaced by its first content reading so that a
    bare אל in a longer query still finds אל³ "God"."""
    from backend.hebrew.processor import homograph_readings, is_unpointed, lemmatize_hebrew
    fallbacks = {}
    lemmas = set(query_lemmas)
    for token in query.split():
        if not is_unpointed(token):
            continue
        for lemma in lemmatize_hebrew([token]):
            readings = [r for r in homograph_readings(lemma) if r not in stopwords] or [lemma]
            canonical = lemma if lemma in readings else readings[0]
            others = set(readings) - {canonical}
            if canonical != lemma and lemma in lemmas:
                lemmas.discard(lemma)
                lemmas.add(canonical)
            if others:
                fallbacks[canonical] = others
    return (fallbacks or None), lemmas


def _line_lemmas_matching_query(line_lemmas, query_lemmas, fallback_forms=None):
    """The lemmas of an indexed line that answer the query: the query lemmas
    themselves and their fallback readings. The index lookup counts a hit on
    מלך² as a hit on מלך, so a line must be judged the same way here; testing
    the line against the query lemmas alone dropped every line that held only
    another reading (bare מלך found "king" but never "he reigned"). The line's
    own readings are returned, so each result names the word it has."""
    accepted = set(query_lemmas)
    for lemma in query_lemmas:
        accepted.update((fallback_forms or {}).get(lemma, ()))
    return set(line_lemmas) & accepted


def _normalize_lemma(lem, language='la'):
    """Normalize a lemma for index lookup. Handles Latin u/v/j/i and Greek diacritics.

    Latin folding applies to Latin ONLY (2026-09-20). It used to fall through
    to every other language, so an English query "love" became "loue",
    "jove" became "ioue" and "voice" became "uoice": the English line search
    then returned only Spenser's spellings (love: 500 Spenser lines and no
    other author; voice: nothing at all), and the results page's corpus
    panel was blank for any shared word with a v or a j. The English index
    stores lemmas as written ("love" 2,193 postings in 124 works, "loue" 553
    in 6), so the query must stay as written too.
    """
    if language == 'grc':
        import unicodedata
        decomposed = unicodedata.normalize('NFD', lem)
        stripped = ''.join(c for c in decomposed if unicodedata.category(c) != 'Mn')
        return stripped.lower().replace('ς', 'σ')
    if language == 'la':
        return _normalize_latin_lemma(lem)
    return lem.lower()


def _score_v3_idf(shared_lemmas, corpus_frequencies, total_corpus_words,
                   distance, phrase_match_bonus=1.0):
    """V3-style scoring: sum(IDF) * distance_factor * phrase_bonus.

    Args:
        shared_lemmas: Set of shared lemma strings.
        corpus_frequencies: Dict mapping lemma → corpus frequency count.
        total_corpus_words: Total word count across corpus.
        distance: Span between first and last matched word positions.
        phrase_match_bonus: Multiplier for phrase matches (default 1.0).

    Returns:
        float score.
    """
    idf_sum = 0
    for lemma in shared_lemmas:
        freq = corpus_frequencies.get(lemma, 1)
        idf = math.log(total_corpus_words / (freq + 1)) + 1
        idf_sum += idf
    distance_factor = 1.0 / (1 + math.log(distance + 1))
    return idf_sum * distance_factor * phrase_match_bonus


def _deduplicate_and_normalize(results):
    """Deduplicate results by text content (keep highest score) and normalize scores to 0-10."""
    import re as _re
    seen_texts = {}
    deduplicated = []
    for r in results:
        text_key = _re.sub(r'[^\w\s]', '', r['text'].lower()).strip()
        if text_key not in seen_texts:
            seen_texts[text_key] = r
            deduplicated.append(r)

    if deduplicated:
        max_score = max(r['score'] for r in deduplicated) or 1
        for r in deduplicated:
            r['raw_score'] = r['score']
            r['score'] = round((r['score'] / max_score) * 10, 2)

    return deduplicated


def _resolve_line_text(source_text_id, line_ref, language):
    """Look up a line's text from its .tess file using the reference tag."""
    source_path = resolve_text_path(TEXTS_DIR, language, source_text_id)
    if source_path:
        with open(source_path, 'r', encoding='utf-8') as f:
            for file_line in f:
                file_line = file_line.strip()
                if file_line.startswith('<') and '>' in file_line:
                    end_tag = file_line.index('>')
                    ref = file_line[1:end_tag].strip()
                    if ref == line_ref:
                        return file_line[end_tag+1:].strip()
    return None


def _build_line_search_stopwords(language, corpus_frequencies):
    """Build stopwords set for line search: default language stops + Zipf elbow detection."""
    from backend.matcher import DEFAULT_LATIN_STOP_WORDS, DEFAULT_GREEK_STOP_WORDS, DEFAULT_ENGLISH_STOP_WORDS
    from backend.zipf import find_zipf_elbow
    from collections import Counter

    if language == 'la':
        stopwords = set(DEFAULT_LATIN_STOP_WORDS)
    elif language == 'grc':
        stopwords = set(DEFAULT_GREEK_STOP_WORDS)
    else:
        stopwords = set(DEFAULT_ENGLISH_STOP_WORDS)

    if corpus_frequencies:
        freq_counter = Counter(corpus_frequencies)
        zipf_stops = find_zipf_elbow(freq_counter, min_stopwords=10, max_stopwords=50)
        stopwords = stopwords.union(zipf_stops)

    return stopwords


def _evaluate_line_candidate(unit, ref, filename, filtered_source_lemmas, query_text_lower,
                              source_text_id, line_ref, key_phrases, corpus_frequencies,
                              total_corpus_words, lang_dates, seen_results, min_matches=2,
                              index_matching_lemmas=None):
    """Evaluate a single candidate line against the source line.

    Used by both the index fast path and the fallback scan path in line_search_parallel().
    Returns a result dict if the candidate passes all filters, or None.

    For the index path, pass index_matching_lemmas (the lemmas the index found).
    For the fallback path, leave it None to compute shared lemmas directly.
    """
    import re as _re

    if not unit:
        return None

    unit_ref = ref or unit.get('ref', '')
    result_key = (filename, unit_ref)
    if result_key in seen_results:
        return None
    seen_results.add(result_key)

    target_text = unit.get('text', '').lower().strip()

    # Exclude the exact source line and lines with identical text
    if filename == source_text_id and unit_ref == line_ref:
        return None
    if target_text == query_text_lower:
        return None

    # Compute shared lemmas (index path verifies against actual lemmas with normalization)
    target_lemmas_list = unit.get('lemmas', [])

    if index_matching_lemmas is not None:
        target_lemmas_normalized = {_normalize_latin_lemma(l) for l in target_lemmas_list}
        source_lemmas_normalized = {_normalize_latin_lemma(l) for l in filtered_source_lemmas}
        matching_normalized = {_normalize_latin_lemma(l) for l in index_matching_lemmas}
        shared = matching_normalized & target_lemmas_normalized & source_lemmas_normalized
    else:
        target_lemmas = set(target_lemmas_list)
        shared = filtered_source_lemmas & target_lemmas

    if len(shared) < min_matches:
        return None

    # Phrase matching — quotation detection
    target_normalized = _re.sub(r'[^\w\s]', '', target_text)
    phrase_match_bonus = 1.0
    for phrase in key_phrases:
        if phrase in target_normalized:
            phrase_match_bonus = 1000.0 + len(phrase) * 100
            break

    # Calculate match positions and distance
    if index_matching_lemmas is not None:
        match_positions = [i for i, lem in enumerate(target_lemmas_list)
                          if _normalize_latin_lemma(lem) in shared]
    else:
        match_positions = [i for i, lem in enumerate(target_lemmas_list) if lem in shared]

    if len(match_positions) >= 2:
        distance = match_positions[-1] - match_positions[0] + 1
    else:
        distance = 1

    max_dist = PROSE_MAX_DISTANCE if is_prose_text_unified(filename) else POETRY_MAX_DISTANCE
    if distance > max_dist:
        return None

    score = _score_v3_idf(shared, corpus_frequencies, total_corpus_words,
                           distance, phrase_match_bonus)

    # Build result
    parts = filename.replace('.tess', '').split('.')
    author_key = filename.split('.')[0].lower()
    author_info = lang_dates.get(author_key, {})

    return {
        'text_id': filename,
        'author': parts[0] if parts else '',
        'work': '.'.join(parts[1:]) if len(parts) > 1 else '',
        'ref': unit_ref,
        'text': unit.get('text', ''),
        'tokens': unit.get('tokens', []),
        'highlight_indices': match_positions,
        'matched_lemmas': list(shared),
        'match_count': len(shared),
        'score': round(score, 3),
        'year': author_info.get('year'),
        'era': author_info.get('era', 'Unknown')
    }


# =============================================================================
# MAIN SEARCH API ROUTES
# =============================================================================
# These routes handle the core search functionality for finding parallel
# passages between source and target texts using various matching algorithms.


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


@api_route('/text/<path:text_id>/lines')
def get_text_lines(text_id):
    """Get lines from a text file for browsing"""
    language = request.args.get('language', '')
    
    if not language:
        for lang in ['la', 'grc', 'en']:
            filepath = resolve_text_path(TEXTS_DIR, lang, text_id)
            if filepath:
                language = lang
                break
    
    filepath = resolve_text_path(TEXTS_DIR, language, text_id)
    
    if not filepath:
        return jsonify({'error': 'Text not found', 'lines': []}), 404
    
    try:
        lines = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or not line.startswith('<'):
                    continue
                try:
                    end_tag = line.index('>')
                    locus = line[1:end_tag].strip()
                    text = line[end_tag+1:].strip()
                    lines.append({'locus': locus, 'text': text})
                except ValueError:
                    continue
        
        return jsonify({
            'text_id': text_id,
            'lines': lines,
            'total': len(lines)
        })
    except Exception as e:
        return jsonify({'error': str(e), 'lines': []}), 500


# =============================================================================
# LINE SEARCH (CORPUS-WIDE) API ROUTES
# =============================================================================
# These routes enable searching for words/phrases across the entire corpus
# using the pre-built inverted index for fast lookups.

def _dedup_same_passage(results):
    """Collapse the SAME passage duplicated across text_ids that vary only by
    author/work naming — e.g. cyprian.ad_demetrianum vs cyprian_saint.ad_demetrianum
    (both locus 23), or arnobius.adversus_nationes vs
    arnobius_of_sicca.adversus_nationes_libri_vii (both 2.59). The whole/part
    text_id dedup misses these because the ids differ.

    Key on (locus, normalized line text): two rows sharing BOTH the exact locus
    label and the exact line are the same passage under a variant spelling.
    Conservative by construction — a repeated refrain has one text but different
    loci (kept), and edition spelling variants differ in text (kept), so this only
    removes genuine duplicate-text inflation, never distinct loci. Rows with empty
    text are always kept (can't confirm they are duplicates). Order preserved.
    """
    seen = set()
    out = []
    for r in results:
        nt = ' '.join((r.get('text') or '').lower().split())
        key = (r.get('locus'), nt)
        if nt and key in seen:
            continue
        if nt:
            seen.add(key)
        out.append(r)
    return out


# A lemma this frequent (as a share of the table's most frequent lemma) is a
# commonplace: quis, ipse, uir and some three hundred friends. 0.45 keeps
# examen (151/767 in Latin) distinctive while catching uarius (481/767).
RARE_FOCUS_COMMON_RATIO = 0.45


def rare_focus_filter(results, language):
    """Drop lemma-search results whose shared words are ALL commonplaces.

    The Reader's Verbal Parallels tab asks this: a line's quid + uariis
    matching Catullus's quid + uarii is not an echo, it is Latin. A result
    survives when at least one shared lemma is distinctive (low document
    frequency), or when three or more distinct lemmas are shared, since the
    CO-OCCURRENCE of several common words is itself distinctive (arma +
    uir + cano). Returns (kept, hidden_count, common_lemmas_seen); on any
    failure (no doc-freq table for the language) returns results unfiltered.
    """
    try:
        import sqlite3 as _sq
        from backend.lexical_density import _index_path
        conn = _sq.connect(f'file:{_index_path(language)}?mode=ro', uri=True)
        max_df = conn.execute('SELECT MAX(df) FROM lemma_doc_freq').fetchone()[0]
        if not max_df:
            conn.close()
            return results, 0, []
        threshold = max_df * RARE_FOCUS_COMMON_RATIO
        df_cache = {}

        def df_of(lem):
            if lem not in df_cache:
                row = conn.execute(
                    'SELECT df FROM lemma_doc_freq WHERE lemma = ?',
                    (lem,)).fetchone()
                df_cache[lem] = row[0] if row else 0
            return df_cache[lem]

        kept, hidden, commons = [], 0, set()
        for r in results:
            distinct = set(r.get('matched_lemmas') or [])
            if not distinct:
                kept.append(r)
                continue
            if len(distinct) >= 3 or any(df_of(l) <= threshold for l in distinct):
                kept.append(r)
            else:
                hidden += 1
                commons.update(distinct)
        conn.close()
        return kept, hidden, sorted(commons)
    except Exception as e:
        # No doc-freq table for this language (or a broken one): filter
        # nothing, but say so — the silent form of this fallback is how the
        # missing Hebrew and Coptic tables went unnoticed last time.
        import logging
        logging.getLogger('tesserae').warning(
            '[RARE-FOCUS] filter unavailable for %s (%s); showing all matches',
            language, e)
        return results, 0, []


def _count_candidates_by_work(text_candidates, language, lang_dates):
    """[{work_id, author, work, year, era, count}] for every work holding a
    co-occurring line, newest-last by year (see line_search). A whole file wins
    over its book files; book files alone are summed."""
    import re as _re_w
    groups = {}
    for filename, matches in text_candidates.items():
        base = _re_w.sub(r'\.part\.[^/]*$', '', filename[:-5] if filename.endswith('.tess') else filename)
        g = groups.setdefault(base, {'whole': None, 'parts': 0, 'file': filename})
        if '.part.' in filename:
            g['parts'] += len(matches)
        else:
            g['whole'] = len(matches)
            g['file'] = filename
    out = []
    for base, g in groups.items():
        count = g['whole'] if g['whole'] is not None else g['parts']
        filepath = resolve_text_path(TEXTS_DIR, language, g['file'])
        meta = get_text_metadata(filepath) if filepath else {}
        info = lang_dates.get(base.split('.')[0].lower(), {})
        out.append({'work_id': base, 'author': meta.get('author') or base.split('.')[0],
                    'work': meta.get('title') or base, 'year': info.get('year'),
                    'era': info.get('era', 'Unknown'), 'count': count})
    out.sort(key=lambda w: (w['year'] if w['year'] is not None else 9999, w['author'], w['work']))
    return out


# =============================================================================
# DOCUMENTS COLLECTION (stage 3b-2/3b-3, behind TESSERAE_DOCUMENTS=1)
# =============================================================================
# Lets /api/line-search search the documentary corpus (inscriptions, papyri;
# PR #678) alongside or instead of literature. See backend/documents.py for
# the index/metadata/sidecar access this reuses. Everything below is reached
# only when `collection` is 'documents' or 'both' AND backend.documents.enabled()
# -- with the switch off, or collection omitted, line_search()'s literary
# path above is completely untouched by any of this.
#
# Stage 3b-3 added restoration marking/exclusion, a stock-formula count and
# filter, and the GET /api/documents/<doc_id> Reader route (further down).

import unicodedata as _documents_ud

# Default threshold for `hide_formulas` (spec item 5): drop a document hit
# whose matched lemmas/phrase co-occur in MORE than this many documents in
# the same index. Measured directly against the real dev documents indexes
# (2026-10-08, la_documents_index.db/grc_documents_index.db), counting
# DISTINCT documents sharing the matched lemma set via
# backend.documents.find_co_occurring_lemmas + doc_for (the same postings
# lookup _documents_formula_count uses):
#   dis manibus                   35,231 documents  (a true formula)
#   bene merenti                  11,903 documents  (a true formula)
#   votum solvit libens merito     3,990 documents  (a true formula)
#   hic situs est                  3,535 documents  (a true formula)
#   arma virumque                     19 documents  (a genuine parallel)
#   arma virumque cano                 8 documents  (a genuine parallel)
# The gap between the smallest formula (3,535) and the largest genuine
# parallel (19) spans three orders of magnitude, so 100 cleanly separates
# them with wide margin on both sides.
DOCUMENTS_FORMULA_DEFAULT_N = 100

# A plain `None` default for `_document_hit`'s `meta_override` would be
# indistinguishable from "looked this id up and it is genuinely
# uncredited" (a real, meaningful value); this sentinel means "the caller
# passed nothing, look it up yourself".
_UNSET = object()


# Stage 4 (the owner's review of the live documents trial, 2026-10-08):
# document results no longer come back in storage order. 'relevance'
# (default) ranks an exact adjacent phrase ahead of one whose matched words
# are scattered across the line, a match resting on surviving text ahead of
# one resting on editorially restored text, then fewer restorations
# elsewhere on the same line, then earliest date. 'oldest'/'newest' sort on
# date alone; 'region' alphabetically. See _document_sort_key.
_DOCUMENT_SORT_MODES = ('relevance', 'oldest', 'newest', 'region')


def _min_adjacent_span_rank(positions_dict, lemmas):
    """0 when the matched lemmas' best-case token positions on this line
    form one unbroken run (an "exact adjacent phrase" per the stage 4
    ranking spec), 1 when they are scattered, or when position data is not
    available for one of them. `positions_dict` is find_co_occurring_
    lemmas' own per-lemma position list for this line (backend.
    inverted_index's `data['positions']`) -- this never fetches or
    re-splits the line's text; a documentary phrase query is short (2-4
    words), and each lemma's own occurrence list on one short epigraphic or
    papyrus line is almost always length 1, so brute-forcing every
    combination of "which occurrence of each lemma" is a handful of
    tuples, never a performance concern even run across tens of thousands
    of candidates."""
    lists = [sorted(set(positions_dict.get(l) or [])) for l in lemmas]
    if not lists:
        return 1
    if len(lists) == 1:
        return 0 if lists[0] else 1
    if any(not lst for lst in lists):
        return 1
    best_span = None
    for combo in itertools.product(*lists):
        span = max(combo) - min(combo)
        if best_span is None or span < best_span:
            best_span = span
    return 0 if best_span == len(lists) - 1 else 1


def _restored_rank_and_extra(all_positions, restored_set):
    """(restored_rank, extra_restorations) for the 'relevance' sort.
    restored_rank: 0 every matched position is on surviving text, 1 some
    are restored, 2 every matched position is restored (mirrors
    _restoration_flags' own matched_restored/partly_restored, as a single
    ordered rank rather than two booleans). extra_restorations: how many
    OTHER token positions on the same line are restored but are not part
    of this match -- the spec's "fewer extra restorations" tiebreak,
    ascending. Both computed from token positions alone (never text)."""
    if not all_positions:
        return 0, len(restored_set)
    restored_matched = sum(1 for p in all_positions if p in restored_set)
    total = len(all_positions)
    if restored_matched == 0:
        rank = 0
    elif restored_matched == total:
        rank = 2
    else:
        rank = 1
    return rank, max(0, len(restored_set) - restored_matched)


def _date_sort_value(m):
    """A document hit's own best single year for sorting/century-bucketing:
    date_not_before, falling back to date_not_after, None when metadata.db
    has neither (an uncredited or undated hit) -- sorted last by
    _document_sort_key, never guessed at as "year zero"."""
    if not m:
        return None
    v = m.get('date_not_before')
    if v is None:
        v = m.get('date_not_after')
    return v


def _document_sort_key(sort, rank):
    """The tuple to sort a document hit's own `rank` dict (built in
    _search_documents_collection: adjacency/restored_rank/
    extra_restorations/date/region/doc_id) ascending on, for `sort` (one of
    _DOCUMENT_SORT_MODES; an unrecognized value is treated as
    'relevance')."""
    date = rank.get('date')
    date_known = date is not None
    if sort == 'oldest':
        return (date_known is False, date if date_known else 0, rank['doc_id'])
    if sort == 'newest':
        return (date_known is False, -date if date_known else 0, rank['doc_id'])
    if sort == 'region':
        region = (rank.get('region') or '').lower()
        return (region == '', region, rank['doc_id'])
    return (rank['adjacency'], rank['restored_rank'], rank['extra_restorations'],
            date_known is False, date if date_known else 0, rank['doc_id'])


def _century_label(year):
    """A document's own date_not_before/after (see _date_sort_value) as a
    century bucket for the distribution chart: classicists' convention, no
    year 0 (year 1 AD is the 1st century AD; year -1, i.e. 1 BC, is the 1st
    century BC). 'Unknown' for an undated hit -- shown as its own bar
    rather than silently dropped."""
    if year is None:
        return 'Unknown'
    if year == 0:
        # No year 0 in this convention (never a real EDH/EDCS/Trismegistos
        # date); a stray 0 is folded into 1st c. AD rather than producing
        # a nonsensical "0th century".
        n, era = 1, 'AD'
    elif year >= 1:
        n, era = (year - 1) // 100 + 1, 'AD'
    else:
        n, era = (-year - 1) // 100 + 1, 'BC'
    if n % 100 in (11, 12, 13):
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix} c. {era}'


def _century_sort_key(label):
    """Chronological order for _century_label's own output: BC centuries
    descending (furthest past first), then AD ascending, 'Unknown' last."""
    if label == 'Unknown':
        return (1, 0)
    n = int(''.join(ch for ch in label.split(' ', 1)[0] if ch.isdigit()))
    era = label.rsplit(' ', 1)[-1]
    return (0, -n if era == 'BC' else n + 10000)


def _tally_source_region(kept):
    """[{source, region, count}] sorted by count descending, over every
    kept candidate's own metadata (not just the page) -- the documents
    analogue of _count_candidates_by_work's by_work_all. `kept` is a list
    of the per-candidate dicts _search_documents_collection builds, each
    carrying a 'meta' key (a backend.documents.meta()-shaped dict, or
    None). `region` is translated (backend.documents.translate_label) the
    same way a result row's own 'region' field is, so a chart or table
    built from this never prints a raw German value either."""
    import backend.documents as docs
    tally = {}
    for k in kept:
        m = k.get('meta') or {}
        region = docs.translate_label(m.get('region')) or 'unknown'
        key = (m.get('source') or 'unknown', region)
        tally[key] = tally.get(key, 0) + 1
    out = [{'source': k[0], 'region': k[1], 'count': v} for k, v in tally.items()]
    out.sort(key=lambda x: -x['count'])
    return out


def _tally_century(kept):
    """[{century, count}] in chronological order, over every kept
    candidate (not just the page) -- the distribution-by-century chart the
    stage 4 spec asks for, computed once per request from metadata already
    fetched for ranking (see _search_documents_collection), not a second
    pass over the index."""
    tally = {}
    for k in kept:
        m = k.get('meta') or {}
        label = _century_label(_date_sort_value(m))
        tally[label] = tally.get(label, 0) + 1
    out = [{'century': label, 'count': v} for label, v in tally.items()]
    out.sort(key=lambda x: _century_sort_key(x['century']))
    return out


def _restoration_flags(matched_positions, restored_set):
    """(matched_restored, partly_restored) for one document hit: whether
    EVERY matched token position is one write_document_tess.py's own
    sidecar marked restored, or only SOME are. Both False when
    `matched_positions` is empty/None (no position information for this
    hit -- never a reason to claim restoration either way) or when none
    of the matched positions are restored."""
    if not matched_positions:
        return False, False
    restored_matched = sum(1 for p in matched_positions if p in restored_set)
    total = len(matched_positions)
    return restored_matched == total, 0 < restored_matched < total


def _normalize_token_for_phrase_match(tok):
    """NFC + lowercase + strip leading/trailing punctuation, so a token
    list built at index time (write_document_tess.py) can be compared
    against an exact-search query's own words without the two text layers
    (editorial brackets, stray punctuation) causing a false miss."""
    tok = _documents_ud.normalize('NFC', tok or '').lower()
    return re.sub(r'^\W+|\W+$', '', tok)


def _find_exact_phrase_positions(tokens, query):
    """Token-index span of an *exact*-search query inside one document
    line's own `tokens` list, best-effort: the first contiguous run whose
    normalized form matches the query word-for-word, with
    exact_phrase_pattern's own asymmetric rule carried over (no trailing
    boundary on the LAST word, so "virum" still matches a line's
    "virumque" -- see backend/utils.py). Returns [] when the query has no
    words, `tokens` is empty, or no such run is found (an exact hit whose
    positions this cannot pin down -- a scan-based SLOW PATH match, not an
    index-driven one, see _search_documents_collection -- simply carries
    no restoration marking, rather than guessing)."""
    words = [_normalize_token_for_phrase_match(w) for w in (query or '').split()]
    if not words or not tokens:
        return []
    norm_tokens = [_normalize_token_for_phrase_match(t) for t in tokens]
    n = len(words)
    for i in range(len(norm_tokens) - n + 1):
        ok = True
        for j in range(n):
            if j == n - 1:
                if not norm_tokens[i + j].startswith(words[j]):
                    ok = False
                    break
            elif norm_tokens[i + j] != words[j]:
                ok = False
                break
        if ok:
            return list(range(i, i + n))
    return []


def _documents_formula_count(language, matched_lemmas, cache):
    """How many documents in this SAME documents index (for `language`)
    share every one of `matched_lemmas` -- the in-N-documents count stage
    3b-3 asks for, computed from postings the same way line search counts
    co-occurrence candidates (backend.documents.find_co_occurring_lemmas,
    which wraps backend.inverted_index's own index-driven lookup), never
    a corpus scan. `cache` is a plain dict the CALLER owns for the life of
    one request (keyed on frozenset(matched_lemmas)): a 2-3 word
    documentary query typically produces the same matched-lemma set
    across most of its hits, so this is usually computed once per query,
    not once per hit, satisfying the "cached per query" requirement
    without a module-level cache that could go stale across requests or
    leak between languages/queries.

    Returns None (never 0-as-a-guess) for an empty lemma set -- a hit
    whose matched_lemmas is empty (the exact/regex SLOW PATH never
    populates matched_lemmas -- see _search_documents_collection) has no
    well-defined "documents sharing this lemma pair" count, and formula
    hiding/display must treat that as unknown, not as "unique"."""
    if not matched_lemmas:
        return None
    key = frozenset(matched_lemmas)
    if key in cache:
        return cache[key]
    import backend.documents as docs
    candidates = docs.find_co_occurring_lemmas(list(key), language, min_matches=len(key))
    distinct_docs = set()
    for filename, ref, _matching_lemmas, _positions in candidates:
        d = docs.doc_for(language, filename, ref)
        if d:
            distinct_docs.add(d)
    count = len(distinct_docs)
    cache[key] = count
    return count


def _lemmatize_query_simple(query, language, text_processor):
    """Query lemmas for a documents-collection search. Documents are Latin
    or Greek only (backend.documents.SUPPORTED_LANGUAGES), so this is the
    plain lemmatizer path line_search()'s own literary branch uses for every
    language except Persian/Urdu/Arabic/Hebrew -- those branches never apply
    here and are not reproduced."""
    query_lemmas = set()
    for token in query.lower().split():
        lemmas = text_processor.lemmatize_word(token, language)
        query_lemmas.update(_normalize_lemma(l, language) for l in lemmas)
    if not query_lemmas:
        query_lemmas = set(_normalize_lemma(t, language) for t in query.lower().split())
    return query_lemmas


def _document_passes_filters(m, date_from, date_to, region, text_type, material, source):
    """True if a document hit's metadata (backend.documents.meta's return,
    or None) satisfies every filter the caller actually set. A filter the
    request left unset is skipped. When NO filter is active this always
    returns True, even with m=None (an uncredited hit is still shown). When
    at least one filter IS active and m is None, the hit cannot be
    confirmed and is excluded -- safer than showing an unfiltered row inside
    a filtered search."""
    if not any([date_from is not None, date_to is not None, region, text_type, material, source]):
        return True
    if m is None:
        return False
    if date_from is not None:
        if m.get('date_not_after') is None or m['date_not_after'] < date_from:
            return False
    if date_to is not None:
        if m.get('date_not_before') is None or m['date_not_before'] > date_to:
            return False
    if region:
        if not m.get('region') or region.lower() not in m['region'].lower():
            return False
    if text_type:
        if not m.get('text_type_label') or text_type.lower() not in m['text_type_label'].lower():
            return False
    if material:
        if not m.get('material_label') or material.lower() not in m['material_label'].lower():
            return False
    if source:
        cred = m.get('credit') or {}
        haystack = ' '.join(str(v) for v in (
            m.get('source'), m.get('collection'),
            cred.get('source_name'), cred.get('source_name_secondary'),
        ) if v).lower()
        if source.lower() not in haystack:
            return False
    return True


def _document_hit(language, filename, ref, matched_words, matched_lemmas, tokens=None,
                   matched_positions=None, formula_count=None, meta_override=_UNSET):
    """One documents-collection result row: credit, date, place, labels and
    restored-word positions from backend.documents, instead of the literary
    author/work/era/year shape. `tokens` (the line's own tokenized form, same
    one restored_indices' positions were computed against at write time) is
    passed through so the client can mark restored words by POSITION rather
    than re-splitting `text` on whitespace, which would drift out of step
    with restored_indices the moment punctuation or an elided editorial mark
    changes the split. Returns (row, meta_or_None) -- meta is handed back so
    the caller does not look metadata up twice for the filter check.

    `matched_positions` (stage 3b-3): the matched tokens' own index
    positions, when the caller could determine them (always true for the
    lemma FAST PATH; best-effort via _find_exact_phrase_positions for
    'exact'; never for 'regex' -- see _search_documents_collection), used
    only to set matched_restored/partly_restored against the sidecar's
    restored-token positions. `formula_count` (stage 3b-3): how many
    documents in this index share the matched lemma pair/phrase -- see
    _documents_formula_count; None when not computed (regex, or an exact
    hit whose matched_lemmas came back empty).

    `meta_override` (stage 4): the caller's own already-fetched metadata
    dict (or None, meaning "looked up and genuinely uncredited"), when it
    has one -- _search_documents_collection's lemma FAST PATH bulk-fetches
    metadata for every candidate up front (backend.documents.bulk_meta) so
    ranking thousands of matches never pays for one metadata.db round trip
    per row; passing the already-known value here avoids looking it up a
    second time. Left at its default (the `_UNSET` sentinel, not None --
    None is itself a valid, meaningful override) this calls
    backend.documents.meta(doc_id) itself, exactly as before stage 4.

    Place/region/material/object/text-type labels are passed through
    backend.documents.translate_label (a handful of EDH/EDCS/Trismegistos
    values are German) before going in the row; ancient_place/modern_place
    are set to None instead when backend.documents.is_unknown_place
    recognizes the raw value as a "place not known" placeholder (German
    'unbekannt', English 'unknown', Latin 'ignoratur') -- stage 4: hidden
    rather than shown translated as the word "unknown", which is no
    information for a reader. The metadata.db value itself is never
    modified by any of this."""
    import backend.documents as docs
    doc_id = docs.doc_for(language, filename, ref)
    if meta_override is not _UNSET:
        m = meta_override
    else:
        m = docs.meta(doc_id) if doc_id else None
    restored = docs.restored_indices(language, filename, ref)
    matched_restored, partly_restored = _restoration_flags(
        matched_positions, set(restored.get('restored') or []))

    def _place(value):
        return None if docs.is_unknown_place(value) else docs.translate_label(value)

    row = {
        'collection': 'documents',
        'doc_id': doc_id,
        'locus': ref,
        'text_id': filename,
        'language': language,
        'text': None,  # filled by the caller, which already has the line text
        'tokens': tokens or [],
        'matched_words': matched_words,
        'matched_lemmas': sorted(matched_lemmas) if matched_lemmas else [],
        'credit': (m or {}).get('credit'),
        'date_not_before': (m or {}).get('date_not_before'),
        'date_not_after': (m or {}).get('date_not_after'),
        'ancient_place': _place((m or {}).get('ancient_place')),
        'modern_place': _place((m or {}).get('modern_place')),
        'region': docs.translate_label((m or {}).get('region')),
        'pleiades_id': (m or {}).get('pleiades_id'),
        'text_type_label': docs.translate_label((m or {}).get('text_type_label')),
        'object_type_label': docs.translate_label((m or {}).get('object_type_label')),
        'material_label': docs.translate_label((m or {}).get('material_label')),
        'source': (m or {}).get('source'),
        'restored_indices': restored.get('restored'),
        'fragment_indices': restored.get('fragment'),
        'matched_restored': matched_restored,
        'partly_restored': partly_restored,
        'formula_count': formula_count,
    }
    return row, m


def _lemma_fast_path_matches(language, filtered_query_lemmas, min_matched):
    """Every (filename, ref, matched_lemmas, positions) the documents index
    has for `filtered_query_lemmas`, with the distance rule already applied
    -- the FULL, uncapped candidate set (stage 4: no 500-row ceiling).
    Cheap: nothing here touches metadata.db, a restored-word sidecar or a
    line's own text; the distance check reuses the index's own per-lemma
    position lists (the same ones find_co_occurring_lemmas returns),
    exactly the way _min_adjacent_span_rank reuses them for ranking,
    instead of re-fetching and re-splitting the line's text the way
    backend.distance_filter.calculate_match_distance does for the literary
    search path."""
    import backend.documents as docs
    from backend.distance_filter import get_max_distance
    out = []
    if not filtered_query_lemmas:
        return out
    candidates = docs.find_co_occurring_lemmas(list(filtered_query_lemmas), language,
                                                 min_matches=min_matched)
    for filename, ref, matching_lemmas, positions in candidates:
        matched_lemmas = set(matching_lemmas) & filtered_query_lemmas
        if len(matched_lemmas) < min_matched:
            continue
        lists = [positions.get(l) or [] for l in matched_lemmas]
        min_dist = 0
        if len(lists) >= 2:
            dists = [abs(pa - pb) for i in range(len(lists)) for j in range(i + 1, len(lists))
                     for pa in lists[i] for pb in lists[j]]
            if dists:
                min_dist = min(dists)
        if min_dist > 0 and min_dist > get_max_distance(filename, language):
            continue
        out.append({'filename': filename, 'ref': ref, 'matched_lemmas': matched_lemmas,
                    'positions': positions})
    return out


def _search_documents_collection(language, search_type, query, filtered_query_lemmas,
                                  min_matched, offset, limit, date_from, date_to,
                                  region, text_type, material, source,
                                  exclude_restored=False, hide_formulas=None,
                                  sort='relevance'):
    """Document hits for the documents/both collection. Mirrors the FAST PATH
    of line_search()'s literary branch (same index-driven candidate lookup,
    same matched-word shape) against backend.documents's own documents-index
    connection, with document fields (credit/date/place/labels/restored
    positions) instead of author/work/era/year.

    Rarity note (spec item 3): a document hit's matched-lemma rarity belongs
    to the DOCUMENTS index's own lemma_doc_freq table, never the literary
    one. This function computes no score at all (same as the literary
    branch -- line_search results are filtered/deduped and sorted by era/
    year/author, never ranked by score) EXCEPT the stage 4 relevance rank
    added below, which is its own self-contained measure (adjacency/
    restoration/date, all read off this collection's own index and
    metadata.db) and never touches the literary lemma_doc_freq table either.

    Stage 3b-3, `exclude_restored`: drop a hit whose match rests ENTIRELY on
    restored tokens (restored_rank == 2, see _restored_rank_and_extra). A hit
    with no position information is never dropped by this (restored_rank is
    0 whenever there are no matched positions, by that function's own
    contract) -- "unknown" and "not restored" are deliberately the same safe
    outcome here.

    Stage 3b-3, `hide_formulas`: drop a hit whose `formula_count` (documents
    in this SAME index sharing its matched lemmas, see
    _documents_formula_count) exceeds this integer. A hit with
    formula_count None (regex; or exact, whose matched_lemmas is always
    empty -- see the SLOW PATH below) is never dropped: an unmeasured count
    is not evidence of a formula, and silently hiding regex/exact documents
    hits whenever this filter is on would be a much bigger behavior change
    than the spec asked for.

    Formula words (data/documents/formula_words_la.txt/_grc.txt, spec item
    6): NOT applied as a down-rank here, and deliberately so: the
    'relevance' sort above is a document-provenance measure (adjacency/
    restoration/date), not a word-rarity one, and there is still no
    mechanism on this path for a soft lexical penalty to attach to.
    Recorded in docs/DECISIONS.md.

    Stage 4 (owner's review of the live trial, 2026-10-08): no 500-row
    ceiling. `offset`/`limit` page a SORTED, FULLY-FILTERED candidate list
    (`sort`, one of _DOCUMENT_SORT_MODES); the per-row cost of building a
    full result row (a line-text fetch, the restored-word sidecar, label
    translation) is paid only for the page actually requested, never for
    the whole candidate set -- see _lemma_fast_path_matches and
    backend.documents.bulk_meta's own docstrings for how ranking and
    filtering stay cheap at tens of thousands of candidates ("dis manibus"
    matches roughly 35,000 of them; measured end-to-end warm latency is in
    docs/DECISIONS.md).

    Returns (page_results, total, by_source_region, by_century, stats).
    `total` is the exact count of matches after EVERY filter (date/region/
    text_type/material/source/exclude_restored/hide_formulas); `by_
    source_region`/`by_century` ([{source,region,count}]/[{century,count}],
    the documents analogue of _count_candidates_by_work's by_work_all) are
    computed over that SAME total, not just the returned page.
    `page_results` is exactly `limit` rows (fewer on the last page) starting
    at `offset`. stats is {'restored_excluded_count',
    'formulas_hidden_count', 'formula_summary'} (formula_summary is None
    for a non-lemma search or an empty lemma set).
    """
    import backend.documents as docs
    stats = {'restored_excluded_count': 0, 'formulas_hidden_count': 0, 'formula_summary': None}
    if language not in docs.SUPPORTED_LANGUAGES or not docs.is_index_available(language):
        return [], 0, [], [], stats
    if search_type not in ('lemma', 'exact', 'regex'):
        search_type = 'lemma'
    if sort not in _DOCUMENT_SORT_MODES:
        sort = 'relevance'

    formula_cache = {}

    if search_type == 'lemma':
        if not filtered_query_lemmas:
            return [], 0, [], [], stats
        raw_candidates = _lemma_fast_path_matches(language, filtered_query_lemmas, min_matched)
        for c in raw_candidates:
            c['doc_id'] = docs.doc_for(language, c['filename'], c['ref'])
        meta_by_id = docs.bulk_meta([c['doc_id'] for c in raw_candidates if c['doc_id']])

        # The stock-formula count for the WHOLE query's lemma set is
        # exactly the distinct-document count this pass already computed,
        # whenever min_matched asked for every one of filtered_query_
        # lemmas (true for the common 2-word documentary phrase) --
        # seeding the cache here saves a second find_co_occurring_lemmas
        # pass purely to recompute the same number.
        if min_matched == len(filtered_query_lemmas):
            stats_doc_ids = {c['doc_id'] for c in raw_candidates if c['doc_id']}
            formula_cache[frozenset(filtered_query_lemmas)] = len(stats_doc_ids)

        kept = []
        for c in raw_candidates:
            m = meta_by_id.get(c['doc_id'])
            if not _document_passes_filters(m, date_from, date_to, region, text_type,
                                             material, source):
                continue
            all_positions = sorted({p for l in c['matched_lemmas']
                                     for p in (c['positions'].get(l) or [])})
            restored = docs.restored_indices(language, c['filename'], c['ref'])
            restored_set = set(restored.get('restored') or [])
            restored_rank, extra_restorations = _restored_rank_and_extra(all_positions, restored_set)
            if exclude_restored and restored_rank == 2:
                stats['restored_excluded_count'] += 1
                continue
            formula_count = _documents_formula_count(language, c['matched_lemmas'], formula_cache)
            if hide_formulas is not None and formula_count is not None and formula_count > hide_formulas:
                stats['formulas_hidden_count'] += 1
                continue
            adjacency = _min_adjacent_span_rank(c['positions'], c['matched_lemmas'])
            kept.append({
                'filename': c['filename'], 'ref': c['ref'], 'doc_id': c['doc_id'],
                'matched_lemmas': c['matched_lemmas'], 'all_positions': all_positions,
                'meta': m, 'formula_count': formula_count,
                'rank': {
                    'adjacency': adjacency, 'restored_rank': restored_rank,
                    'extra_restorations': extra_restorations,
                    'date': _date_sort_value(m), 'region': (m or {}).get('region'),
                    'doc_id': c['doc_id'] or '',
                },
            })

        total = len(kept)
        by_source_region = _tally_source_region(kept)
        by_century = _tally_century(kept)
        kept.sort(key=lambda k: _document_sort_key(sort, k['rank']))
        page = kept[offset:offset + limit]

        # Only the page's own rows pay for a line-text fetch, grouped by
        # filename exactly as the pre-stage-4 code did for every
        # candidate -- one batched get_lines_batch call per filename
        # touched by this page (almost always far fewer than `limit`
        # files), never one call per candidate.
        by_filename = {}
        for p in page:
            by_filename.setdefault(p['filename'], []).append(p['ref'])
        lines_by_filename = {filename: (docs.get_lines_batch(filename, refs, language) or {})
                              for filename, refs in by_filename.items()}

        page_results = []
        for p in page:
            line_info = lines_by_filename.get(p['filename'], {}).get(p['ref']) or {}
            text = line_info.get('text', '')
            tokens = line_info.get('tokens') or []
            matched_positions = sorted(pos for pos in p['all_positions'] if pos < len(tokens))
            matched_words = [tokens[i] for i in matched_positions]
            row, _m = _document_hit(language, p['filename'], p['ref'], matched_words,
                                     p['matched_lemmas'], tokens=tokens,
                                     matched_positions=matched_positions,
                                     formula_count=p['formula_count'], meta_override=p['meta'])
            row['text'] = text
            page_results.append(row)

        if filtered_query_lemmas:
            stats['formula_summary'] = {
                'query_lemmas': sorted(filtered_query_lemmas),
                'documents_sharing_all': _documents_formula_count(
                    language, filtered_query_lemmas, formula_cache),
            }
        return page_results, total, by_source_region, by_century, stats

    # exact/regex: no index path exists for these (same as the literary
    # SLOW PATH), so scan every line of every bucket file for `language`
    # through the documents index's own `lines` table -- reusing the SAME
    # connection the lemma path above uses. This already had no cheaper
    # path before stage 4; the only change here is removing the fixed
    # 500-row ceiling and running the full result set through the same
    # sort/paginate/distribution pass the lemma path above uses.
    conn = docs.get_connection(language)
    if conn is None:
        return [], 0, [], [], stats
    exact_pattern = exact_phrase_pattern(query) if search_type == 'exact' else None
    try:
        text_rows = conn.execute('SELECT text_id, filename FROM texts').fetchall()
    except Exception:                                               # noqa: BLE001
        return [], 0, [], [], stats

    seen = set()
    kept = []
    for trow in text_rows:
        filename = trow['filename']
        try:
            line_rows = conn.execute(
                'SELECT ref, content, tokens FROM lines WHERE text_id = ?', (trow['text_id'],)
            ).fetchall()
        except Exception:                                           # noqa: BLE001
            continue
        for lrow in line_rows:
            ref, text = lrow['ref'], (lrow['content'] or '')
            if (filename, ref) in seen:
                continue
            match_found = False
            if search_type == 'exact':
                if exact_pattern and exact_pattern.search(exact_search_text(text)):
                    match_found = True
            else:
                try:
                    if re.search(query, text, re.IGNORECASE):
                        match_found = True
                except re.error:
                    pass
            if not match_found:
                continue
            matched_words = query.split() if search_type == 'exact' else []
            try:
                row_tokens = json.loads(lrow['tokens']) if lrow['tokens'] else []
            except Exception:                                        # noqa: BLE001
                row_tokens = []
            # Best-effort token positions for 'exact' only (see
            # _find_exact_phrase_positions); 'regex' has no well-defined
            # phrase span to locate, so matched_positions stays [] and
            # matched_restored/partly_restored both come back False.
            matched_positions = (_find_exact_phrase_positions(row_tokens, query)
                                  if search_type == 'exact' else [])
            if not passes_distance_filter(text, matched_words, filename, language):
                continue
            doc_id = docs.doc_for(language, filename, ref)
            m = docs.meta(doc_id) if doc_id else None
            if not _document_passes_filters(m, date_from, date_to, region, text_type,
                                             material, source):
                continue
            restored = docs.restored_indices(language, filename, ref)
            restored_set = set(restored.get('restored') or [])
            restored_rank, extra_restorations = _restored_rank_and_extra(matched_positions, restored_set)
            if exclude_restored and restored_rank == 2:
                stats['restored_excluded_count'] += 1
                continue
            seen.add((filename, ref))
            # No per-lemma position dict exists on this SLOW PATH (no
            # lemma match at all for 'regex'; 'exact' has no co-occurrence
            # concept to be "scattered" relative to) -- an exact/regex hit
            # is ranked as an exact adjacent phrase by construction.
            kept.append({
                'filename': filename, 'ref': ref, 'doc_id': doc_id, 'text': text,
                'tokens': row_tokens, 'matched_words': matched_words,
                'matched_positions': matched_positions, 'meta': m,
                'rank': {
                    'adjacency': 0, 'restored_rank': restored_rank,
                    'extra_restorations': extra_restorations,
                    'date': _date_sort_value(m), 'region': (m or {}).get('region'),
                    'doc_id': doc_id or '',
                },
            })

    total = len(kept)
    by_source_region = _tally_source_region(kept)
    by_century = _tally_century(kept)
    kept.sort(key=lambda k: _document_sort_key(sort, k['rank']))
    page = kept[offset:offset + limit]
    page_results = []
    for p in page:
        row, _m = _document_hit(language, p['filename'], p['ref'], p['matched_words'], set(),
                                 tokens=p['tokens'], matched_positions=p['matched_positions'],
                                 formula_count=None, meta_override=p['meta'])
        row['text'] = p['text']
        page_results.append(row)
    return page_results, total, by_source_region, by_century, stats


def _line_search_documents_only(query, language, search_type, offset, limit, sort, count_only,
                                 date_from, date_to, region, text_type, material, source,
                                 search_start_time, exclude_restored=False, hide_formulas=None):
    """Full /api/line-search response for collection='documents': the
    documentary corpus alone, no literary search run at all. Returns a Flask
    response directly (line_search() returns this immediately).

    Stage 4: `offset`/`limit` page the (now uncapped) result list 50 rows at
    a time by default, ranked by `sort`; the payload's 'total'/
    'distinct_loci' are the TRUE total after every filter, never a 500-row
    lower bound -- see _search_documents_collection's own docstring."""
    import time as time_module
    import backend.documents as docs

    filtered_query_lemmas = set()
    filtered_common_words = []
    if search_type == 'lemma' and language in docs.SUPPORTED_LANGUAGES:
        from backend.matcher import DEFAULT_LATIN_STOP_WORDS, DEFAULT_GREEK_STOP_WORDS
        stopwords = set(DEFAULT_LATIN_STOP_WORDS if language == 'la' else DEFAULT_GREEK_STOP_WORDS)
        query_lemmas = _lemmatize_query_simple(query, language, text_processor)
        content_lemmas = query_lemmas - stopwords
        filtered_query_lemmas = content_lemmas if len(content_lemmas) >= 2 else query_lemmas
        filtered_common_words = sorted(query_lemmas - content_lemmas)
    elif language in docs.SUPPORTED_LANGUAGES:
        filtered_query_lemmas = set(_normalize_lemma(t, language) for t in query.lower().split())

    min_matched = max(1, min(2, len(filtered_query_lemmas))) if search_type == 'lemma' else 1

    results, total, by_source_region, by_century, doc_stats = _search_documents_collection(
        language, search_type, query, filtered_query_lemmas, min_matched, offset, limit,
        date_from, date_to, region, text_type, material, source,
        exclude_restored=exclude_restored, hide_formulas=hide_formulas, sort=sort)

    search_time = round(time_module.time() - search_start_time, 3)
    payload = {
        'collection': 'documents',
        'total': total,
        'distinct_loci': total,
        'query': query,
        'search_time': search_time,
        'capped': False,
        'sort': sort,
        'pagination': {'offset': offset, 'limit': limit, 'total': total},
        'corpus_version': docs.get_corpus_version(language),
    }
    if filtered_common_words:
        payload['filtered_common_words'] = filtered_common_words
    if by_source_region:
        payload['documents_by_source_region'] = by_source_region
        payload['lines_all'] = sum(w['count'] for w in by_source_region)
    if by_century:
        payload['documents_by_century'] = by_century
    if exclude_restored:
        payload['restored_excluded_count'] = doc_stats['restored_excluded_count']
    if hide_formulas is not None:
        payload['formulas_hidden_count'] = doc_stats['formulas_hidden_count']
    if doc_stats['formula_summary']:
        payload['formula_summary'] = doc_stats['formula_summary']
    if not count_only:
        payload['results'] = results
    return jsonify(payload)


@api_route('/documents/<doc_id>', methods=['GET'])
def get_document(doc_id):
    """Stage 3b-3's document Reader view: one documentary text's own lines
    (from the documents index's `lines` table, via `doc_meta`), restored/
    fragment positions per line, credit, date/place/labels, and the stage
    3a display fields (museum, inventory, dimensions, translation,
    apparatus, commentary, image links) from metadata.db's `display`
    table. Behind TESSERAE_DOCUMENTS=1 (404 otherwise, same as the search
    side of this feature being entirely absent with the switch off); a
    live site additionally gates this at the client with the ?documents=1
    trial (see LineSearch.jsx), same as the search control itself.

    `doc_id` alone does not say which language's documents index it lives
    in (ids are source-prefixed, e.g. "edh:HD047322", not language-coded),
    so an explicit `?language=la|grc` is tried first; without one, every
    language in backend.documents.SUPPORTED_LANGUAGES is tried in turn
    and the first hit wins -- doc ids are unique across sources within a
    language by construction (stage 3a's merged corpus id), and no case
    of a document id colliding across la/grc has ever been seen in a real
    build, but a future dual-language corpus could reconsider this.
    """
    import backend.documents as docs
    if not docs.enabled():
        return jsonify({'error': 'not found'}), 404
    requested_language = (request.args.get('language') or '').strip().lower()
    languages_to_try = ([requested_language] if requested_language in docs.SUPPORTED_LANGUAGES
                         else list(docs.SUPPORTED_LANGUAGES))
    doc_data = None
    found_language = None
    for lang in languages_to_try:
        if not docs.is_index_available(lang):
            continue
        doc_data = docs.get_document_lines(lang, doc_id)
        if doc_data is not None:
            found_language = lang
            break
    if doc_data is None:
        return jsonify({'error': 'document not found'}), 404

    m = docs.meta(doc_id) or {}
    display = docs.display_fields(doc_id)
    payload = {
        'doc_id': doc_id,
        'language': found_language,
        'text_id': doc_data['filename'],
        'lines': doc_data['lines'],
        'credit': m.get('credit'),
        'collection': m.get('collection'),
        'source': m.get('source'),
        'date_not_before': m.get('date_not_before'),
        'date_not_after': m.get('date_not_after'),
        'ancient_place': m.get('ancient_place'),
        'modern_place': m.get('modern_place'),
        'region': m.get('region'),
        'pleiades_id': m.get('pleiades_id'),
        'text_type_label': m.get('text_type_label'),
        'object_type_label': m.get('object_type_label'),
        'material_label': m.get('material_label'),
        'display': display or {},
    }
    return jsonify(payload)


@api_route('/documents/<doc_id>/scholarship', methods=['GET'])
def get_document_scholarship(doc_id):
    """Journal sentences and commentary notes that cite one document, from
    the offline document citation index: citation, one excerpt and a link,
    newest first, never summarised. Behind TESSERAE_DOCUMENTS=1 like the
    document view itself (404 otherwise); an absent index file gives an empty
    list."""
    import backend.documents as _docs_mod
    if not _docs_mod.enabled():
        return jsonify({'error': 'not found'}), 404
    from backend.document_scholarship import scholarship_for
    return jsonify(dict(scholarship_for(doc_id), doc_id=doc_id))


@api_route('/documents/browse', methods=['GET'])
def browse_documents():
    """The Documents section of Browse Corpus: a normalized facet tree
    (kind -> region -> century, each with counts; for papyri, region ->
    findspot -> century -- see `findspot_counts`) plus the flat filters
    (text type, material, object type, language) and one page of matching
    documents. Behind TESSERAE_DOCUMENTS=1 (404 otherwise, same as the rest
    of this feature); see backend/documents_browse.py for the normalization
    rules and the in-memory facet cache this reads.
    """
    import backend.documents as _docs_mod
    if not _docs_mod.enabled():
        return jsonify({'error': 'not found'}), 404
    import backend.documents_browse as browse_mod

    def _arg(name):
        v = (request.args.get(name) or '').strip()
        return v or None

    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.args.get('page_size', browse_mod.DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = browse_mod.DEFAULT_PAGE_SIZE

    result = browse_mod.browse(
        kind=_arg('kind'), region=_arg('region'), findspot=_arg('findspot'), century=_arg('century'),
        text_type=_arg('text_type'), material=_arg('material'),
        object_type=_arg('object'), language=_arg('language'),
        page=page, page_size=page_size)

    # First-line snippets are a per-document index lookup each; only done
    # for the one page actually being returned, and best-effort (see
    # first_line_for -- None on any miss, never an error for the request).
    for doc in result['documents']:
        doc['first_line'] = browse_mod.first_line_for(doc['doc_id'], doc.get('language'))

    return jsonify(result)


@api_route('/line-search', methods=['GET', 'POST'])
def line_search():
    """
    Search for words/phrases across the corpus with optional filters.
    Uses inverted index for fast lookups when available.
    """
    try:
        from backend.inverted_index import is_index_available, find_co_occurring_lemmas, has_lines_data, get_lines_batch, get_corpus_version
        from backend.distance_filter import passes_distance_filter, is_prose_text as is_prose_text_unified
        
        # Accept both POST JSON bodies and GET query-string params, so any
        # assistant that can only fetch a URL can still run this search.
        data = request.get_json(silent=True) or request.args

        query = data.get('query', '')
        language = data.get('language', 'la')
        search_type = data.get('search_type', 'lemma')
        author_filter = data.get('author', '')
        work_filter = data.get('work', '')
        line_start = data.get('line_start')
        line_end = data.get('line_end')
        # Coerce to int: on a GET request query-string params arrive as strings,
        # and max_results is compared with `len(results) >= max_results`.
        try:
            max_results = int(data.get('max_results', 500))
        except (TypeError, ValueError):
            max_results = 500
        if max_results <= 0:
            max_results = 500

        # count_only: return just the deduped corpus counts (total / distinct_loci
        # / capped) and skip the results payload. Quantifying a "commonplace" for
        # the per-entry corpus-context rule then costs a tiny response instead of
        # hundreds of passages. Accept truthy strings on GET.
        count_only = data.get('count_only', False)
        if isinstance(count_only, str):
            count_only = count_only.strip().lower() in ('1', 'true', 'yes', 'on')

        # rare_focus: opt-in (the Reader's Verbal Parallels tab sets it). Hide
        # results whose shared words are all commonplaces; see
        # rare_focus_filter. The Line Search page never sets it, so deliberate
        # common-word queries there behave exactly as before.
        rare_focus = data.get('rare_focus', False)
        if isinstance(rare_focus, str):
            rare_focus = rare_focus.strip().lower() in ('1', 'true', 'yes', 'on')

        # Documents collection (stage 3b-2, behind TESSERAE_DOCUMENTS=1): search
        # literature (default, today's exact behaviour), the documentary corpus
        # (inscriptions/papyri), or both. Omitting `collection` entirely, or the
        # switch being off, must leave every byte of the response unchanged —
        # so the literary code path below is never altered by this parameter;
        # it is only ever read at the two insertion points this stage added
        # (the early documents-only return, and the pre-return merge for
        # 'both'). See backend/documents.py.
        collection = (data.get('collection') or 'literature').strip().lower()
        if collection not in ('literature', 'documents', 'both'):
            collection = 'literature'
        import backend.documents as _docs_mod
        documents_active = collection in ('documents', 'both') and _docs_mod.enabled()

        def _coerce_year(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None
        date_from = _coerce_year(data.get('date_from')) if documents_active else None
        date_to = _coerce_year(data.get('date_to')) if documents_active else None
        doc_region_filter = (data.get('region') or '').strip() if documents_active else ''
        doc_text_type_filter = (data.get('text_type') or '').strip() if documents_active else ''
        doc_material_filter = (data.get('material') or '').strip() if documents_active else ''
        doc_source_filter = (data.get('source') or '').strip() if documents_active else ''

        # Stage 3b-3: leave out a document hit whose match rests entirely on
        # restored text (documents/both only -- see _restoration_flags).
        doc_exclude_restored = False
        if documents_active:
            doc_exclude_restored = data.get('exclude_restored', False)
            if isinstance(doc_exclude_restored, str):
                doc_exclude_restored = doc_exclude_restored.strip().lower() in ('1', 'true', 'yes', 'on')

        # Stage 3b-3: hide a document hit whose matched lemmas/phrase co-occur
        # in more than N documents in this same index (a stock formula --
        # see _documents_formula_count and DOCUMENTS_FORMULA_DEFAULT_N).
        # Off by default; the caller passes an integer (any int, including 0)
        # to turn it on, so `0` is a valid, deliberately strict threshold, not
        # treated as falsy-and-ignored.
        doc_hide_formulas = None
        if documents_active:
            _hide_formulas_raw = data.get('hide_formulas')
            if _hide_formulas_raw not in (None, ''):
                try:
                    doc_hide_formulas = int(_hide_formulas_raw)
                except (TypeError, ValueError):
                    doc_hide_formulas = None

        # Stage 4 (owner's review of the live trial, 2026-10-08): document
        # hits no longer stop at a fixed 500-row ceiling (a stock phrase
        # like "dis manibus" is in roughly 35,000 of them) -- they are
        # paged server-side (`doc_offset`/`doc_limit`, 50 rows per page by
        # default, `doc_limit` clamped to that range so a request cannot
        # ask this endpoint to build an unbounded page) and ranked by
        # `doc_sort` (see _DOCUMENT_SORT_MODES/_document_sort_key): default
        # 'relevance' puts an exact adjacent phrase ahead of scattered
        # words, a match on surviving text ahead of one resting on restored
        # words, fewer extra restorations, then earliest date; 'oldest'/
        # 'newest' sort on date alone; 'region' sorts alphabetically.
        doc_sort = 'relevance'
        doc_offset = 0
        doc_limit = 50
        if documents_active:
            doc_sort = (data.get('sort') or 'relevance').strip().lower()
            if doc_sort not in _DOCUMENT_SORT_MODES:
                doc_sort = 'relevance'
            try:
                doc_offset = max(0, int(data.get('offset', 0)))
            except (TypeError, ValueError):
                doc_offset = 0
            try:
                doc_limit = int(data.get('limit', 50))
            except (TypeError, ValueError):
                doc_limit = 50
            doc_limit = max(1, min(50, doc_limit))

        # Source exclusion - don't include the source line in results
        exclude_text_id = data.get('exclude_text_id', '')
        exclude_locus = data.get('exclude_locus', '')
        
        line_text = data.get('line_text', '')
        
        if query:
            import time as time_module
            search_start_time = time_module.time()

            # collection='documents': the documentary corpus alone, no
            # literary search at all. Returns here; nothing below this
            # block runs, so it cannot affect the literary path (collection
            # omitted, or 'literature', or the switch off) in any way.
            if collection == 'documents' and documents_active:
                return _line_search_documents_only(
                    query, language, search_type, doc_offset, doc_limit, doc_sort, count_only,
                    date_from, date_to, doc_region_filter, doc_text_type_filter,
                    doc_material_filter, doc_source_filter, search_start_time,
                    exclude_restored=doc_exclude_restored, hide_formulas=doc_hide_formulas)
            if collection == 'documents' and not documents_active:
                # Documents requested but the switch is off, or this
                # language has no documents index: literature's own
                # behaviour is the only sane fallback (never a silent
                # empty result), so fall through to it unchanged.
                collection = 'literature'

            try:
                from backend.metrical_scanner import is_prose_text
            except ImportError:
                from metrical_scanner import is_prose_text
            lang_dir = os.path.join(TEXTS_DIR, language)
            lang_dates = AUTHOR_DATES.get(language, {})
            
            if not os.path.exists(lang_dir):
                return jsonify({'results': [], 'total': 0})
            
            # Build stoplist: ALWAYS include base stopwords (ab, et, in, etc.) 
            # plus optionally top N corpus-frequent lemmas
            from backend.matcher import DEFAULT_LATIN_STOP_WORDS, DEFAULT_GREEK_STOP_WORDS, DEFAULT_ENGLISH_STOP_WORDS
            
            # Start with base stopwords for the language
            if language == 'la':
                stopwords = set(DEFAULT_LATIN_STOP_WORDS)
            elif language == 'grc':
                stopwords = set(DEFAULT_GREEK_STOP_WORDS)
            elif language == 'en':
                stopwords = set(DEFAULT_ENGLISH_STOP_WORDS)
            else:
                # Persian, Urdu, Arabic, Coptic, Hebrew: the language's own
                # curated list. The English list applied here left every
                # Persian particle searchable, and one line of Hafez took
                # eleven minutes (2026-09-07).
                # Production's matcher has no language plugins yet (they come
                # with the Persian, Urdu and Arabic work), so fall back to the
                # list this branch always used.
                try:
                    from backend.matcher import _plugin_stoplist
                except ImportError:
                    _plugin_stoplist = None
                stopwords = set((_plugin_stoplist(language) if _plugin_stoplist else None)
                                or DEFAULT_ENGLISH_STOP_WORDS)
            
            # Optionally add top N corpus-frequent lemmas
            stoplist_size = data.get('stoplist_size', 10)
            corpus_freq_data = get_corpus_frequencies(language, text_processor)
            corpus_frequencies = corpus_freq_data.get('frequencies', {}) if corpus_freq_data else {}
            if stoplist_size > 0 and corpus_frequencies:
                sorted_lemmas = sorted(corpus_frequencies.items(), key=lambda x: x[1], reverse=True)
                stopwords.update(lemma for lemma, _ in sorted_lemmas[:stoplist_size])
            
            query_lemmas = set()
            # THE INDEX ALREADY KNOWS THE LEMMAS OF ITS OWN LINES. When the
            # Reader asks about lines of a work (it names them in `refs`, or
            # the first in exclude_text_id + exclude_locus), their lemmas are
            # read from the index's lines table instead of re-tagged. For
            # Persian, Urdu and Arabic re-tagging meant loading Stanza inside
            # the web process (gigabytes, minutes; the app grew to 10 GB).
            _stanza_langs = ('fa', 'ur', 'ar')
            _ref_list = [str(r) for r in (data.get('refs') or []) if r]
            if not _ref_list and data.get('exclude_text_id') and data.get('exclude_locus'):
                _stem = str(data['exclude_text_id']).replace('.tess', '')
                _ref_list = [f"{_stem}.{data['exclude_locus']}"]
            # Only for those three languages. On production the index path
            # changed Latin Reader results (Aeneid 1.33 came back empty on
            # 2026-09-11) because the index's lemma spellings differ from the
            # lemmatizer's; Latin, Greek and the rest keep the lemmatizer.
            if (search_type == 'lemma' and language in _stanza_langs and _ref_list
                    and data.get('exclude_text_id') and has_lines_data(language)):
                _stem = str(data['exclude_text_id']).replace('.tess', '')
                _rows = get_lines_batch(f'{_stem}.tess', _ref_list, language)
                for _row in _rows.values():
                    query_lemmas.update(_normalize_lemma(l, language) for l in (_row.get('lemmas') or []) if l)
            if search_type == 'lemma' and not query_lemmas:
                query_tokens = query.lower().split()
                try:
                    from backend.perso_arabic import _base_normalize
                except ImportError:
                    # The Persian, Urdu and Arabic normalizer lives on the
                    # preview branch; without it every language takes the
                    # lemmatizer path below.
                    _base_normalize = None
                if language in _stanza_langs and _base_normalize is not None:
                    # A typed query in these languages is searched by its
                    # normalized surface forms (the language's own normalizer,
                    # the one the index lemmas went through); nouns and most
                    # words are their own lemma, and no tagger runs here.
                    from backend.perso_arabic import _base_normalize
                    from backend.surface_lemmas import lemma_for
                    query_lemmas = set()
                    for t in query_tokens:
                        n = _base_normalize(t, language)
                        if not n:
                            continue
                        # The lemma the tagger gave this form when it built the
                        # index, from a table over the lemma caches. Without it
                        # an inflected form ("الديار") matched nothing, since
                        # the index is keyed by lemma ("دار"). The lemma
                        # replaces the form: the search wants every query
                        # lemma in the line, so a form that is not itself a
                        # lemma would rule every line out (2026-09-08).
                        lem = lemma_for(n, language)
                        query_lemmas.add(lem or n)
                else:
                    for token in query_tokens:
                        lemmas = text_processor.lemmatize_word(token, language)
                        query_lemmas.update(_normalize_lemma(l, language) for l in lemmas)
                if not query_lemmas:
                    query_lemmas = set(_normalize_lemma(t, language) for t in query_tokens)
            else:
                query_lemmas = set(_normalize_lemma(t, language) for t in query.lower().split())
            
            # A Hebrew query typed without vowel points: each lemma also
            # matches its other homograph readings (אל typed bare finds "to",
            # "not" and "God"), through the index's fallback forms.
            query_fallback_forms = None
            if language == 'he' and search_type == 'lemma':
                query_fallback_forms, query_lemmas = _hebrew_unpointed_fallbacks(query, query_lemmas, stopwords)

            # Filter out stopwords from query lemmas (like pairwise search)
            content_lemmas = query_lemmas - stopwords
            filtered_query_lemmas = content_lemmas
            if len(filtered_query_lemmas) < 2:
                # Restore the common words so the co-occurrence search can still
                # run — a two-word query whose second word is too common to index
                # on its own is still a PAIR query, not a single-word one.
                filtered_query_lemmas = query_lemmas

            # Words dropped as too-common, named in the response so a reduced
            # multi-word query is not silently answered as a different question.
            filtered_common_words = sorted(query_lemmas - content_lemmas)
            n_query_words = len([w for w in query.split() if w.strip()])

            # A PASSAGE-SIZED QUERY SEARCHES ON ITS RAREST WORDS. The Reader's
            # Verbal Parallels tab sends the whole selection as one query; six
            # Aeneid lines lemmatize to 40 lemmas, whose posting lists union to
            # 269,850 candidate lines and 97 seconds of search (measured
            # 2026-08-29). Two shared words out of 40
            # is also a commonplace, not a parallel. So above a cap the query
            # keeps only its rarest lemmas by corpus document frequency, which
            # is both the fast search and the Tesserae-shaped question: lines
            # sharing the passage's DISTINCTIVE vocabulary. The reduction is
            # named in the response, never silent.
            LEMMA_CAP = 12
            reduced_from = None
            if len(filtered_query_lemmas) > LEMMA_CAP:
                try:
                    import sqlite3 as _sq
                    from backend.lexical_density import _index_path
                    _conn = _sq.connect(f'file:{_index_path(language)}?mode=ro',
                                        uri=True)
                    _df = {}
                    for _lem in filtered_query_lemmas:
                        _r = _conn.execute(
                            'SELECT df FROM lemma_doc_freq WHERE lemma = ?',
                            (_lem,)).fetchone()
                        _df[_lem] = _r[0] if _r else 0
                    _conn.close()
                    _present = [l for l in filtered_query_lemmas if _df[l] > 0]
                    if len(_present) > LEMMA_CAP:
                        reduced_from = len(filtered_query_lemmas)
                        filtered_query_lemmas = set(
                            sorted(_present, key=lambda l: _df[l])[:LEMMA_CAP])
                except Exception as _e:
                    # No doc-freq table for this language: search as-is, but say
                    # so, because the silent form of this fallback is how the
                    # missing Hebrew and Coptic tables went unnoticed.
                    app.logger.warning(
                        '[LINE-SEARCH] passage-query reduction unavailable for '
                        '%s (%s); searching on all %d lemmas', language, _e,
                        len(filtered_query_lemmas))

            # Single-word count_only: route here ONLY when the query LITERALLY has
            # one word. A multi-word query that common-word filtering reduces to a
            # single content word is still a co-occurrence (pair) query and must
            # run the pair search with the common word restored — reclassifying it
            # as single-word silently turned countable pairings like "bis nostra"
            # (22 places) into a work-count for "bis" (368 works). A one-word query
            # can't co-occur with anything, so answer how common the word is across
            # the corpus (document frequency) instead of a silent zero.
            if count_only and n_query_words <= 1:
                from backend.blueprints.hapax import get_document_frequencies_batch
                if content_lemmas:
                    dfs = get_document_frequencies_batch(content_lemmas, language)
                    df = max(dfs.values()) if dfs else 0
                    return jsonify({
                        'query': query,
                        'single_word': True,
                        'unit': 'works',
                        'corpus_document_frequency': df,
                        'total': df,
                        'corpus_version': get_corpus_version(language),
                        'note': ('single-word query: count is the number of works that contain '
                                 'this word, not co-occurring word pairs'),
                    })
                return jsonify({
                    'query': query, 'single_word': True, 'total': None, 'unquantified': True,
                    'corpus_version': get_corpus_version(language),
                    'note': 'query has no content words to count (all stopwords)',
                })

            results = []
            seen_results = set()
            by_work_all = None
            
            # FAST PATH: Use inverted index if available (O(1) lookup vs O(n) scan).
            # A single-word query (one content lemma) has nothing to co-occur with,
            # so it just lists the lines that contain the word (min_matches=1);
            # multi-word queries still require the pair to co-occur (min_matches=2).
            # 1 for a single-word query, 2 for multi-word; never 0 (an empty
            # lemma set would otherwise admit every line — it also can't reach the
            # fast-path guard below, but max(1,...) makes that safety explicit).
            min_matched = max(1, min(2, len(filtered_query_lemmas)))
            if search_type == 'lemma' and is_index_available(language) and len(filtered_query_lemmas) >= 1:
                candidates = find_co_occurring_lemmas(list(filtered_query_lemmas), language, min_matches=min_matched, fallback_forms=query_fallback_forms)
                use_indexed_lines = has_lines_data(language)
                
                # Group candidates by text
                text_candidates = {}
                for filename, ref, matching_lemmas, positions in candidates:
                    if filename not in text_candidates:
                        text_candidates[filename] = []
                    text_candidates[filename].append((ref, matching_lemmas, positions))

                # EVERY WORK'S COUNT, NOT JUST THE FIRST 500 LINES (2026-10-07).
                # The line list stops at max_results in index order, so for a
                # common pair (Persian "man ast") it held lines from two or three
                # poets and the corpus chart left out the very authors compared.
                # The index already returned every co-occurring line, so counting
                # them per work costs nothing. A work held both whole and in book
                # files is counted once: the whole file when present, else the sum
                # of its books. Counted before the line-level distance filter, so
                # these are the lines that contain the words, a ceiling on matches.
                by_work_all = _count_candidates_by_work(text_candidates, language, lang_dates)
                
                for filename, matches in text_candidates.items():
                    filepath = resolve_text_path(TEXTS_DIR, language, filename)
                    if not filepath:
                        continue
                    
                    metadata = get_text_metadata(filepath)
                    if author_filter and metadata['author'] != author_filter:
                        continue
                    if work_filter and filename != work_filter and metadata['title'] != work_filter:
                        continue
                    
                    author_key = filename.split('.')[0].lower()
                    author_info = lang_dates.get(author_key, {})
                    era = author_info.get('era', 'Unknown')
                    # None (not the 9999 sentinel) for an unknown year, so it does
                    # not leak into output and plot as year 9999 on a timeline.
                    year = author_info.get('year')

                    # Get line data from index
                    refs_needed = [ref for ref, _, _ in matches]
                    lines_data = {}
                    if use_indexed_lines:
                        lines_data = get_lines_batch(filename, refs_needed, language) or {}
                    
                    # Fallback: build a lookup from the actual file if lines_data is empty
                    file_lines_lookup = {}
                    if not lines_data:
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                                for line in f:
                                    line = line.strip()
                                    if line.startswith('<') and '>' in line:
                                        tag_end = line.index('>')
                                        line_ref = line[1:tag_end]
                                        line_text = line[tag_end+1:].strip()
                                        file_lines_lookup[line_ref] = line_text
                        except Exception:
                            app_logger.exception(f"Error loading lines for {filename}")
                    
                    for ref, matching_lemmas, positions in matches:
                        result_key = (filename, ref)
                        if result_key in seen_results:
                            continue
                        
                        # Get text from index or fallback to file lookup
                        line_info = lines_data.get(ref)
                        if line_info:
                            text = line_info.get('text', '')
                        elif ref in file_lines_lookup:
                            text = file_lines_lookup[ref]
                            line_info = None  # Mark as file fallback
                        else:
                            continue  # Skip if no text available
                        
                        # Canonical short locus: strips CTS URNs and text-id
                        # prefixes (Hebrew "hebrew_bible.isaiah.34.11" -> "34.11").
                        locus = format_short_locus(ref)
                        
                        # Find matched words in text using pre-indexed lemmas
                        matched_words = []
                        matched_lemma_set = set()
                        indexed_lemmas = set(line_info.get('lemmas', [])) if line_info else set()
                        indexed_tokens = line_info.get('tokens', []) if line_info else []

                        # Use indexed data if available, otherwise fallback to quick token matching
                        if indexed_lemmas:
                            # Match query lemmas (and a bare Hebrew word's
                            # other readings) against indexed lemmas
                            matching_query_lemmas = _line_lemmas_matching_query(
                                indexed_lemmas, filtered_query_lemmas, query_fallback_forms)
                            if matching_query_lemmas:
                                matched_lemma_set = set(matching_query_lemmas)
                                # Find the actual words that correspond to matching lemmas
                                for i, lemma in enumerate(line_info.get('lemmas', [])):
                                    if lemma in matching_query_lemmas and i < len(indexed_tokens):
                                        matched_words.append(indexed_tokens[i])
                        else:
                            # Quick fallback: just check token overlap without full lemmatization
                            text_tokens = set(re.sub(r'[^\w\s]', '', text.lower()).split())
                            for token in text_tokens:
                                if token in filtered_query_lemmas:
                                    matched_words.append(token)
                                    matched_lemma_set.add(token)
                        
                        if len(set(matched_words)) < min_matched:
                            continue
                        
                        # Exclude source line if specified (normalize both sides for robust matching)
                        if exclude_text_id and exclude_locus:
                            # Normalize text_id comparison (handle with/without .tess, case-insensitive)
                            exclude_text_normalized = exclude_text_id.replace('.tess', '').lower()
                            filename_normalized = filename.replace('.tess', '').lower()
                            # Normalize locus comparison (clean CTS format on both sides)
                            exclude_locus_clean = clean_cts_reference(exclude_locus) if exclude_locus else ''
                            locus_clean = clean_cts_reference(locus) if locus else ''
                            if filename_normalized == exclude_text_normalized and locus_clean == exclude_locus_clean:
                                continue
                        
                        # Distance filter
                        if not passes_distance_filter(text, matched_words, filename, language):
                            continue
                        
                        seen_results.add(result_key)
                        results.append({
                            'text_id': filename,
                            'author': metadata['author'],
                            'work': metadata['title'],
                            'locus': locus,
                            'text': text,
                            'era': era,
                            'year': year,
                            'is_poetry': not is_prose_text_unified(filename, language),
                            'matched_words': matched_words,
                            # Distinct query lemmas this line shares, for
                            # rarity-aware filtering downstream (rare_focus).
                            # The scan path below sets the same field.
                            'matched_lemmas': sorted(matched_lemma_set)
                        })
                        
                        if len(results) >= max_results:
                            break
                    
                    if len(results) >= max_results:
                        break
            
            else:
                # SLOW PATH: Fallback to file scanning (for exact/regex search)
                # Compile the exact-phrase pattern once (whole-word-start matching).
                # Hebrew: users type unpointed queries, but the corpus text is
                # pointed (niqqud + cantillation). Strip pointing from the query
                # here and from each line before the regex runs, so an unpointed
                # exact search matches the pointed text (pointed text is kept for
                # display). See strip_hebrew_pointing.
                he_exact = (search_type == 'exact' and language == 'he')
                exact_query = strip_hebrew_pointing(query) if he_exact else query
                exact_pattern = exact_phrase_pattern(exact_query) if search_type == 'exact' else None
                text_files = [f for f in os.listdir(lang_dir) if f.endswith('.tess')]
                
                for filename in text_files:
                    filepath = os.path.join(lang_dir, filename)
                    metadata = get_text_metadata(filepath)
                    
                    if author_filter and metadata['author'] != author_filter:
                        continue
                    if work_filter and filename != work_filter and metadata['title'] != work_filter:
                        continue
                    
                    author_key = filename.split('.')[0].lower()
                    author_info = lang_dates.get(author_key, {})
                    era = author_info.get('era', 'Unknown')
                    # None (not the 9999 sentinel) for an unknown year, so it does
                    # not leak into output and plot as year 9999 on a timeline.
                    year = author_info.get('year')

                    with open(filepath, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if not line or not line.startswith('<'):
                                continue
                            
                            try:
                                end_tag = line.index('>')
                                full_locus = line[1:end_tag].strip()
                                text = line[end_tag+1:].strip()
                                locus = format_short_locus(full_locus)
                            except ValueError:
                                continue
                            
                            if line_start or line_end:
                                try:
                                    parts = locus.split()
                                    line_num = int(parts[-1]) if parts else 0
                                    if line_start and line_num < line_start:
                                        continue
                                    if line_end and line_num > line_end:
                                        continue
                                except (ValueError, IndexError):
                                    pass
                            
                            match_found = False
                            if search_type == 'exact':
                                # Whole-word-start match (see _exact_phrase_pattern):
                                # excludes substring hits like "quot" inside "aliquot".
                                # Hebrew matches on the pointing-stripped layer; other
                                # languages are NFC-normalized so a precomposed Greek query
                                # matches text stored decomposed (Homer Il. 1.1 μῆνιν ἄειδε
                                # is NFD in the corpus). Both normalize the query side too.
                                match_text = strip_hebrew_pointing(text) if he_exact else exact_search_text(text)
                                if he_exact and ('[' in match_text or '(' in match_text):
                                    # Qere/ketiv, printed "[qere] (ketiv)" or
                                    # "(ketiv) [qere]": a phrase may run through
                                    # EITHER reading. Linearize both readings of the
                                    # line and match if either contains the phrase,
                                    # so exact search for the qere or the ketiv form
                                    # both find the verse.
                                    qere_line = re.sub(r'\[([^\[\]]+)\]\s*\(([^()]+)\)', r'\1', match_text)
                                    qere_line = re.sub(r'\(([^()]+)\)\s*\[([^\[\]]+)\]', r'\2', qere_line)
                                    ketiv_line = re.sub(r'\[([^\[\]]+)\]\s*\(([^()]+)\)', r'\2', match_text)
                                    ketiv_line = re.sub(r'\(([^()]+)\)\s*\[([^\[\]]+)\]', r'\1', ketiv_line)
                                    if exact_pattern and (exact_pattern.search(qere_line) or exact_pattern.search(ketiv_line)):
                                        match_found = True
                                elif exact_pattern and exact_pattern.search(match_text):
                                    match_found = True
                            elif search_type == 'regex':
                                try:
                                    if re.search(query, text, re.IGNORECASE):
                                        match_found = True
                                except re.error:
                                    pass
                            else:
                                text_lower = text.lower()
                                text_words = set(re.sub(r'[^\w\s]', '', text_lower).split())
                                text_lemmas = set()
                                for word in text_words:
                                    lemmas = text_processor.lemmatize_word(word, language)
                                    text_lemmas.update(lemmas)
                                text_lemmas.update(text_words)
                                
                                # Use filtered query lemmas (without stopwords)
                                if filtered_query_lemmas & text_lemmas:
                                    match_found = True
                            
                            if match_found:
                                matched_words = []
                                matched_lemmas = set()  # Track unique lemmas matched (excluding stopwords)
                                if search_type == 'lemma':
                                    for word in re.sub(r'[^\w\s]', '', text.lower()).split():
                                        word_lemmas = text_processor.lemmatize_word(word, language)
                                        word_lemmas.add(word)
                                        # Only count matches with filtered lemmas (no stopwords)
                                        shared_lemmas = word_lemmas & filtered_query_lemmas
                                        if shared_lemmas:
                                            matched_words.append(word)
                                            matched_lemmas.update(shared_lemmas)
                                elif search_type == 'exact':
                                    # The exact pattern already required the whole adjacent
                                    # phrase, so every query word is present. Count them ALL,
                                    # including stopwords — they are part of the phrase the user
                                    # asked for (e.g. "ad Scythiam"), not co-occurrence noise to
                                    # filter. Without this, a phrase containing a stopword falls
                                    # below the 2-word threshold and is silently dropped.
                                    for word in query.split():
                                        wl = word.lower()
                                        matched_words.append(wl)
                                        matched_lemmas.add(wl)
                                else:
                                    for word in query.lower().split():
                                        if word in text.lower() and word not in stopwords:
                                            matched_words.append(word)
                                            matched_lemmas.add(word)
                                
                                # Co-occurrence (lemma/regex) search needs at least 2 distinct
                                # lemmas — a single word in isolation is not a co-occurrence.
                                # Exact-phrase search is different: the user asked for that
                                # specific phrase, so a single-word query is a complete and
                                # valid match and must not be dropped here (issue #502: Coptic
                                # single-word exact queries returned nothing).
                                if search_type != 'exact' and len(matched_lemmas) < 2:
                                    continue
                                
                                # Exclude source line if specified (normalize both sides for robust matching)
                                if exclude_text_id and exclude_locus:
                                    exclude_text_normalized = exclude_text_id.replace('.tess', '').lower()
                                    filename_normalized = filename.replace('.tess', '').lower()
                                    exclude_locus_clean = clean_cts_reference(exclude_locus) if exclude_locus else ''
                                    locus_clean = clean_cts_reference(locus) if locus else ''
                                    if filename_normalized == exclude_text_normalized and locus_clean == exclude_locus_clean:
                                        continue
                                
                                # UNIFIED DISTANCE FILTERING (same logic as pairwise search)
                                if not passes_distance_filter(text, matched_words, filename, language):
                                    continue
                                
                                results.append({
                                    'text_id': filename,
                                    'author': metadata['author'],
                                    'work': metadata['title'],
                                    'locus': locus,
                                    'text': text,
                                    'era': era,
                                    'year': year,
                                    'is_poetry': not is_prose_text_unified(filename, language),
                                    'matched_words': matched_words,
                                    # The distinct query lemmas this line shares,
                                    # for rarity-aware filtering downstream.
                                    'matched_lemmas': sorted(matched_lemmas)
                                })
                                
                                if len(results) >= max_results:
                                    break
                    
                    if len(results) >= max_results:
                        break
            
            # Sort results: first by era (chronological), then by year, then alphabetically by author
            era_order = {
                'Biblical': -1,
                'Archaic': 0, 'Early Greek': 1, 'Classical': 2, 'Hellenistic': 3,
                'Republic': 4, 'Late Republican': 5, 'Late Republic': 5,
                'Augustan': 6, 'Early Imperial': 7, 'Imperial': 8, 
                'Later Imperial': 9, 'Late Antique': 10, 'Patristic': 10,
                'Carolingian': 11, 'Medieval': 12, 'Renaissance': 13, 
                'Early Modern': 14, 'Modern': 15, 'Unknown': 99
            }
            results.sort(key=lambda x: (
                era_order.get(x.get('era', 'Unknown'), 50),
                x.get('year') if x.get('year') is not None else 9999,
                x.get('author', '').lower()
            ))
            
            search_time = round(time_module.time() - search_start_time, 3)

            # Whether the corpus scan hit the result cap. When it did, `total`
            # is a floor, not an exact count — callers should report "N+" rather
            # than a false precise number. (The build loop breaks as soon as
            # len(results) reaches max_results.)
            capped = len(results) >= max_results

            # Collapse the corpus's whole-work vs .part.N duplication: e.g.
            # vergil.eclogues.tess and vergil.eclogues.part.1.tess both report
            # Eclogues 1.43, so an undeduped list double-counts the same line and
            # inflates the corpus-uniqueness signal (~2x for parted works). Key on
            # the .part.N-stripped text_id plus locus (whole and part normalize to
            # the same id; their `work` labels differ — "Eclogues" vs "Eclogues,
            # Book 1" — so we cannot key on work). Different works keep distinct
            # ids. Prefer the whole-work row as the canonical representative.
            import re as _re_dl

            def _base_tid(tid):
                return _re_dl.sub(r'\.part\.\d+.*\.tess$', '.tess', tid) if tid else tid

            _pos = {}
            _deduped = []
            for r in results:
                k = (_base_tid(r.get('text_id')) or r.get('author'), r.get('locus'))
                if k not in _pos:
                    _pos[k] = len(_deduped)
                    _deduped.append(r)
                else:
                    idx = _pos[k]
                    if '.part.' in (_deduped[idx].get('text_id') or '') and '.part.' not in (r.get('text_id') or ''):
                        _deduped[idx] = r
            results = _deduped

            # Second pass: collapse the SAME passage duplicated across text_ids
            # that vary only by author/work naming (see _dedup_same_passage).
            results = _dedup_same_passage(results)

            rare_focus_report = None
            if rare_focus and search_type == 'lemma':
                results, _hidden, _commons = rare_focus_filter(results, language)
                if _hidden:
                    rare_focus_report = {
                        'hidden': _hidden,
                        'common_lemmas': _commons,
                    }

            distinct_loci = len(results)
            payload = {
                'total': distinct_loci,
                'distinct_loci': distinct_loci,
                'query': query,
                'search_time': search_time,
                'capped': capped,
                'corpus_version': get_corpus_version(language),
            }
            if capped:
                # `total`/`distinct_loci` are a lower bound under the cap.
                payload['total_at_least'] = distinct_loci
            if filtered_common_words:
                # A common word in the query was too frequent to index on its own;
                # it WAS still used for co-occurrence. Naming it lets the caller say
                # the pairing leans on the other word rather than mis-report rarity.
                payload['filtered_common_words'] = filtered_common_words
            if rare_focus_report:
                payload['rare_focus'] = rare_focus_report
            if reduced_from:
                payload['query_reduced'] = {
                    'from_lemmas': reduced_from,
                    'to_lemmas': sorted(filtered_query_lemmas),
                    'note': ('Passage-sized query: searched on its '
                             f'{len(filtered_query_lemmas)} rarest words'),
                }
            if by_work_all is not None:
                payload['by_work_all'] = by_work_all
                payload['lines_all'] = sum(w['count'] for w in by_work_all)

            # collection='both': append the documentary corpus's own hits
            # after the literary ones, reusing the SAME filtered_query_lemmas/
            # min_matched this literary search already computed above (for
            # la/grc, line_search's literary lemma extraction takes the same
            # plain-lemmatizer path _line_search_documents_only uses on its
            # own, so this is the identical query, not a re-derived one).
            # 'total'/'distinct_loci' above stay LITERATURE-ONLY (unchanged
            # meaning for every existing caller); the documents count is
            # reported separately rather than folded in, so a connector or
            # script already reading 'total' as "how many places in the
            # corpus" is not silently handed a different number depending on
            # a parameter it may not have sent.
            if collection == 'both' and documents_active:
                # min_matched is only ever assigned inside the FAST (index)
                # path above; the SLOW (exact/regex, or no-index) path never
                # sets it, so it is recomputed here with the same formula
                # rather than assumed to exist.
                _docs_min_matched = (max(1, min(2, len(filtered_query_lemmas)))
                                      if search_type == 'lemma' else 1)
                (doc_results, doc_total, doc_by_source_region, doc_by_century,
                 doc_stats) = _search_documents_collection(
                    language, search_type, query, filtered_query_lemmas, _docs_min_matched,
                    doc_offset, doc_limit, date_from, date_to, doc_region_filter,
                    doc_text_type_filter, doc_material_filter, doc_source_filter,
                    exclude_restored=doc_exclude_restored, hide_formulas=doc_hide_formulas,
                    sort=doc_sort)
                payload['collection'] = 'both'
                # Stage 4: 'documents_total' is now the TRUE total (every
                # match after filters), not a count of a 500-row-capped
                # list -- see _search_documents_collection's own docstring.
                payload['documents_total'] = doc_total
                payload['documents_sort'] = doc_sort
                payload['documents_pagination'] = {
                    'offset': doc_offset, 'limit': doc_limit, 'total': doc_total}
                if doc_by_source_region:
                    payload['documents_by_source_region'] = doc_by_source_region
                    payload['documents_lines_all'] = sum(w['count'] for w in doc_by_source_region)
                if doc_by_century:
                    payload['documents_by_century'] = doc_by_century
                if doc_exclude_restored:
                    payload['restored_excluded_count'] = doc_stats['restored_excluded_count']
                if doc_hide_formulas is not None:
                    payload['formulas_hidden_count'] = doc_stats['formulas_hidden_count']
                if doc_stats['formula_summary']:
                    payload['formula_summary'] = doc_stats['formula_summary']
                if not count_only:
                    results = results + doc_results

            if not count_only:
                payload['results'] = results
            return jsonify(payload)
        
        elif line_text or data.get('source_text_id'):
            pass
        else:
            return jsonify({'error': 'Provide query or line_text'}), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@api_route('/line-search-parallel', methods=['POST'])
def line_search_parallel():
    """
    Search a single line against the entire corpus using inverted index for speed.
    
    Uses pre-built inverted index (lemma → locations) for O(1) candidate lookup,
    then scores only the matching lines instead of scanning all texts.
    """
    try:
        from backend.inverted_index import is_index_available, find_co_occurring_lemmas, has_lines_data, get_lines_batch
        
        data = request.get_json() or {}
        
        line_text = data.get('line_text', '')
        line_ref = data.get('line_ref', '')
        source_text_id = data.get('source_text_id', '')
        language = data.get('language', 'la')
        match_type = data.get('match_type', 'lemma')
        max_results = data.get('max_results', 100)
        max_per_text = data.get('max_per_text', 5)
        min_matches = data.get('min_matches', 2)
        exclude_source = data.get('exclude_source', True)
        use_index = data.get('use_index', True)
        stoplist_size = data.get('stoplist_size', 10)
        
        if not line_text and not (source_text_id and line_ref):
            return jsonify({'error': 'Provide line_text or source_text_id + line_ref'}), 400
        
        if source_text_id and line_ref and not line_text:
            line_text = _resolve_line_text(source_text_id, line_ref, language) or ''
        
        if not line_text:
            return jsonify({'error': 'Could not find the specified line'}), 404
        
        source_unit = text_processor.process_line(line_text, language)
        source_lemmas = set(source_unit.get('lemmas', []))
        
        if len(source_lemmas) < 1:
            return jsonify({'error': 'No lemmas found in the line'}), 400
        
        # Extract key phrases for exact phrase matching
        query_normalized = re.sub(r'[^\w\s]', '', line_text.lower())
        query_tokens = query_normalized.split()
        
        # Build phrase patterns: ONLY the first 2-3 word phrase (distinctive opening)
        # This ensures we find "arma virumque" quotations, not just any shared words
        key_phrases = []
        # Primary: first 3 words (most distinctive)
        if len(query_tokens) >= 3:
            key_phrases.append(' '.join(query_tokens[0:3]))
        # Secondary: first 2 words
        if len(query_tokens) >= 2:
            key_phrases.append(' '.join(query_tokens[0:2]))
        
        lang_dir = os.path.join(TEXTS_DIR, language)
        lang_dates = AUTHOR_DATES.get(language, {})
        
        if not os.path.exists(lang_dir):
            return jsonify({'results': [], 'total': 0, 'texts_searched': 0})
        
        # Get corpus-wide frequencies for global IDF
        corpus_freq_data = get_corpus_frequencies(language, text_processor)
        corpus_frequencies = corpus_freq_data.get('frequencies', {}) if corpus_freq_data else {}
        total_corpus_words = sum(corpus_frequencies.values()) if corpus_frequencies else 1
        
        # Use same stoplist as pairwise search: default language stops + Zipf elbow detection
        stopwords = _build_line_search_stopwords(language, corpus_frequencies)
        
        # Filter source lemmas to exclude stopwords AND short words (same as Matcher)
        # Matcher uses len(lemma) > 2 filter
        # Normalize lemmas for index lookup (Greek diacritics, Latin u/v)
        source_lemmas = {_normalize_lemma(l, language) for l in source_lemmas}
        filtered_source_lemmas = {l for l in source_lemmas if l not in stopwords and len(l) > 2}
        if len(filtered_source_lemmas) < min_matches:
            # Fallback: include longer stopwords if too few content words
            filtered_source_lemmas = {l for l in source_lemmas if len(l) > 2}
        
        all_results = []
        texts_searched = 0
        seen_results = set()
        query_text_lower = line_text.lower().strip()

        # Try to use inverted index for fast lookup
        if use_index and is_index_available(language):
            # FAST PATH: Use inverted index
            candidates = find_co_occurring_lemmas(list(filtered_source_lemmas), language, min_matches)
            
            # Group candidates by text for efficient processing
            text_candidates = {}
            for filename, ref, matching_lemmas, positions in candidates:
                if exclude_source and filename == source_text_id:
                    continue
                if filename not in text_candidates:
                    text_candidates[filename] = []
                text_candidates[filename].append((ref, matching_lemmas, positions))
            
            texts_searched = len(text_candidates)
            
            # Check if we can use the fast path with indexed line data
            use_indexed_lines = has_lines_data(language)
            
            for filename, matches in text_candidates.items():
                filepath = os.path.join(lang_dir, filename)

                # Get line data - FAST: from index, SLOW: from file
                refs_needed = set(ref for ref, _, _ in matches)
                units_by_ref = {}
                
                if use_indexed_lines:
                    # Try fast path first: get lines from the index
                    lines_data = get_lines_batch(filename, list(refs_needed), language)
                    if lines_data:
                        units_by_ref = {ref: {'ref': ref, 'text': data['text'], 'lemmas': data['lemmas'], 'tokens': data['tokens']} 
                                        for ref, data in lines_data.items()}
                
                # Check for any missing refs and fall back to file for those
                missing_refs = refs_needed - set(units_by_ref.keys())
                if missing_refs:
                    if os.path.exists(filepath):
                        file_units = get_processed_units(filename, language, 'line', text_processor)
                        file_units_by_ref = {u.get('ref', ''): u for u in file_units}
                        for ref in missing_refs:
                            if ref in file_units_by_ref:
                                units_by_ref[ref] = file_units_by_ref[ref]
                
                text_matches = []
                for ref, matching_lemmas, positions in matches:
                    unit = units_by_ref.get(ref)
                    result = _evaluate_line_candidate(
                        unit, ref, filename, filtered_source_lemmas, query_text_lower,
                        source_text_id, line_ref, key_phrases, corpus_frequencies,
                        total_corpus_words, lang_dates, seen_results, min_matches,
                        index_matching_lemmas=matching_lemmas)
                    if result:
                        text_matches.append(result)

                text_matches.sort(key=lambda x: x['score'], reverse=True)
                all_results.extend(text_matches[:max_per_text])
        else:
            # FALLBACK: Scan all texts (original behavior)
            text_files = [f for f in os.listdir(lang_dir) if f.endswith('.tess')]
            if exclude_source and source_text_id:
                text_files = [f for f in text_files if f != source_text_id]
            
            for filename in text_files:
                texts_searched += 1
                units = get_processed_units(filename, language, 'line', text_processor)

                text_matches = []
                for unit in units:
                    result = _evaluate_line_candidate(
                        unit, unit.get('ref', ''), filename, filtered_source_lemmas,
                        query_text_lower, source_text_id, line_ref, key_phrases,
                        corpus_frequencies, total_corpus_words, lang_dates,
                        seen_results, min_matches)
                    if result:
                        text_matches.append(result)

                text_matches.sort(key=lambda x: x['score'], reverse=True)
                all_results.extend(text_matches[:max_per_text])
        
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        all_results = _deduplicate_and_normalize(all_results)
        
        final_results = all_results[:max_results] if max_results > 0 else all_results
        
        user_id = current_user.id if current_user and current_user.is_authenticated else None
        city, country, _ip = get_user_location()
        log_search('Line Search', language, source_text_id, None, line_text,
                  match_type, len(all_results), False, user_id, city, country, _ip)
        
        return jsonify({
            'results': final_results,
            'total': len(all_results),
            'displayed': len(final_results),
            'texts_searched': texts_searched,
            'query_line': line_text,
            'query_ref': line_ref if line_ref else 'Manual Query',
            'query_text_id': source_text_id if source_text_id else 'custom_query',
            'query_lemmas': list(filtered_source_lemmas),
            'all_lemmas': list(source_lemmas),
            'stopwords_filtered': list(stopwords & source_lemmas)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_route('/corpus-search', methods=['POST'])
def corpus_search():
    """Search the entire corpus for lines containing specific lemmas using inverted index"""
    try:
        from backend.inverted_index import is_index_available, find_co_occurring_lemmas, has_lines_data, get_lines_batch
        
        data = request.get_json() or {}
        lemmas = data.get('lemmas', [])
        language = data.get('language', 'la')
        exclude_texts = data.get('exclude_texts', [])
        sort_by = data.get('sort_by', 'chronological')

        # Exclude the WHOLE work family of each excluded text, not just the exact
        # filename: the corpus carries a combined file AND per-book parts of the
        # same work (e.g. milton.paradise_lost.tess + .part.1.tess), so excluding
        # the compared text must also drop its duplicate variants, or a phrase
        # unique to the two compared texts leaks back through a part file.
        def _work_base(fn):
            return re.sub(r'\.part\.\d+.*$', '', re.sub(r'\.tess$', '', fn or ''))
        _excluded_bases = {_work_base(f) for f in exclude_texts}
        
        if not lemmas or len(lemmas) < 1:
            return jsonify({'error': 'At least 1 lemma required'}), 400
        
        lang_dates = AUTHOR_DATES.get(language, {})
        
        if not is_index_available(language):
            return jsonify({'error': 'Index not available for this language'}), 400

        # Normalize lemmas for index lookup (strip Greek diacritics, Latin u/v)
        normalized_lemmas = [_normalize_lemma(l, language) for l in lemmas]
        # Drop function words so corpus co-occurrence is driven by content words,
        # not grammatical particles. Critical for Coptic, whose lemmatizer emits
        # article/tense-marker morphemes (ⲡ "the", ⲁ past-marker, ...) that
        # co-occur in nearly every clause and otherwise flood the results.
        from backend.fusion import _STOPLISTS as _FUSION_STOPLISTS
        _stop = _FUSION_STOPLISTS.get(language, set())
        normalized_lemmas = [l for l in normalized_lemmas if l and l.lower() not in _stop]
        if not normalized_lemmas:
            return jsonify({'results': [], 'total': 0, 'lemmas': lemmas})
        matches = find_co_occurring_lemmas(normalized_lemmas, language, min_matches=min(2, len(normalized_lemmas)))
        
        results = []
        text_matches = {}
        text_genre_cache = {}
        
        for filename, ref, matching_lemmas, positions in matches:
            if _work_base(filename) in _excluded_bases:
                continue
            if filename not in text_genre_cache:
                text_genre_cache[filename] = not is_prose_text_unified(filename, language)

            is_poetry = text_genre_cache[filename]
            max_distance = POETRY_MAX_DISTANCE if is_poetry else PROSE_MAX_DISTANCE
            
            all_positions = []
            for lemma in matching_lemmas:
                if lemma in positions:
                    all_positions.extend(positions[lemma])
            if len(all_positions) >= 2:
                all_positions.sort()
                span = all_positions[-1] - all_positions[0]
                if span > max_distance:
                    continue
            
            if filename not in text_matches:
                text_matches[filename] = []
            text_matches[filename].append((ref, matching_lemmas, positions))
        
        for filename, refs_data in text_matches.items():
            filepath = resolve_text_path(TEXTS_DIR, language, filename)
            if not filepath:
                continue
            if not os.path.exists(filepath):
                continue
            metadata = get_text_metadata(filepath)
            # Computed once per text, not once per row: a result page can
            # hold a couple thousand rows sharing the same handful of texts.
            display_name = metadata.get('display_name') or metadata.get('author') or filename
            author_key = filename.split('.')[0].lower()
            author_info = lang_dates.get(author_key, {})
            author_year = author_info.get('year')
            author_era = author_info.get('era', 'Unknown')
            author_note = author_info.get('note', '')
            is_poetry = text_genre_cache.get(filename, False)
            
            refs = [r[0] for r in refs_data]
            
            if has_lines_data(language):
                lines_data = get_lines_batch(filename, refs, language)
            else:
                lines_data = {}
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.startswith('<'):
                                end_tag = line.find('>')
                                if end_tag > 0:
                                    line_ref = line[1:end_tag]
                                    if line_ref in refs:
                                        line_text = line[end_tag+1:].strip()
                                        lines_data[line_ref] = {'text': line_text, 'tokens': [], 'lemmas': []}
                except Exception:
                    app_logger.exception(f"Error loading text snippet for {filename}")
            
            for ref, matching_lemmas, positions in refs_data:
                line_info = lines_data.get(ref, {})
                text = line_info.get('text', '')
                if not text:
                    continue
                tokens = line_info.get('tokens', [])
                token_lemmas = line_info.get('lemmas', [])
                
                matched_indices = []
                lemma_set = set(lemmas)
                for i, lemma in enumerate(token_lemmas):
                    if lemma in lemma_set:
                        matched_indices.append(i)

                # Clean locus + full citation, the same way Line Search builds
                # them (same formula as backend.utils.build_citation, inlined
                # here with the per-text display_name computed once above
                # rather than once per row). `locus` used to be the raw .tess
                # tag, which is what made the browser's tag-parsing fallback
                # necessary in the first place (issue #566); the server now
                # does the job here instead.
                clean_locus = format_short_locus(ref)
                citation = f"{display_name} {clean_locus}".strip() if clean_locus else display_name

                results.append({
                    'text_id': filename,
                    'author': metadata['author'],
                    'title': metadata['title'],
                    'locus': clean_locus,
                    'citation': citation,
                    'text': text,
                    'matched_lemmas': list(matching_lemmas),
                    'highlight_indices': matched_indices,
                    'tokens': tokens,
                    'year': author_year,
                    'era': author_era,
                    'date_note': author_note,
                    'is_poetry': is_poetry
                })
        
        if sort_by == 'chronological':
            results.sort(key=lambda x: (x['year'] if x['year'] is not None else 9999, x['author'], x['title'], x['locus']))
        else:
            results.sort(key=lambda x: (x['author'], x['title'], x['locus']))
        
        return jsonify({
            'results': results[:500],
            'total': len(results),
            'lemmas': lemmas
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_route('/request', methods=['POST'])
def submit_request():
    """Submit a text upload request with optional file attachment"""
    # Handle both JSON and multipart form data
    if request.content_type and 'multipart/form-data' in request.content_type:
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        author = request.form.get('author', '').strip()
        work = request.form.get('work', '').strip()
        language = request.form.get('language', 'latin').strip()
        notes = request.form.get('notes', '').strip()
        e_source = request.form.get('e_source', '').strip()
        e_source_url = request.form.get('e_source_url', '').strip()
        print_source = request.form.get('print_source', '').strip()
        content = ''
        
        # Handle file upload
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename:
                try:
                    content = file.read().decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        file.seek(0)
                        content = file.read().decode('latin-1')
                    # `except Exception`, not a bare except: a bare one also
                    # swallows KeyboardInterrupt and SystemExit, so a worker
                    # being shut down mid-upload answered with a polite error
                    # instead of stopping (code review, 2026-09-21).
                    except Exception:
                        return jsonify({'error': 'Could not read file. Please ensure it is a plain text file.'}), 400
    else:
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        author = data.get('author', '').strip()
        work = data.get('work', '').strip()
        language = data.get('language', 'latin')
        notes = data.get('notes', '').strip()
        e_source = data.get('e_source', '').strip()
        e_source_url = data.get('e_source_url', '').strip()
        print_source = data.get('print_source', '').strip()
        content = data.get('content', '').strip()
    
    language = (language or '').strip().lower()
    allowed_languages = {'latin', 'greek', 'english'}
    try:
        from backend.coptic import COPTIC_ENABLED
        if COPTIC_ENABLED:
            allowed_languages.add('coptic')
    except ImportError:
        pass
    try:
        from backend.hebrew import HEBREW_ENABLED
        if HEBREW_ENABLED:
            allowed_languages.add('hebrew')
    except ImportError:
        pass
    try:
        from backend.persian import PERSIAN_ENABLED
        if PERSIAN_ENABLED:
            allowed_languages.add('persian')
    except ImportError:
        pass
    try:
        from backend.urdu import URDU_ENABLED
        if URDU_ENABLED:
            allowed_languages.add('urdu')
    except ImportError:
        pass
    try:
        from backend.arabic import ARABIC_ENABLED
        if ARABIC_ENABLED:
            allowed_languages.add('arabic')
    except ImportError:
        pass

    # Only author and work are required
    if not author or not work:
        return jsonify({'error': 'Author and work title are required'}), 400
    if language not in allowed_languages:
        return jsonify({'error': f'Please select a valid language ({", ".join(sorted(allowed_languages))})'}), 400
    
    try:
        with get_db_cursor() as cur:
            cur.execute('''
                INSERT INTO text_requests (
                    name, email, author, work, language, notes, content,
                    e_source, e_source_url, print_source
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                name, email, author, work, language, notes, content,
                e_source, e_source_url, print_source
            ))
            result = cur.fetchone()
            request_id = result[0] if result else None
        
        try:
            notify_text_request({
                'name': name, 'email': email, 'author': author,
                'work': work, 'language': language, 'notes': notes,
                'has_file': bool(content)
            })
        except Exception as notify_err:
            app_logger.warning(f"Failed to send text request notification: {notify_err}")
        
        return jsonify({'success': True, 'id': request_id})
    except Exception as e:
        app_logger.error(f"Failed to submit text request: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# USER FEEDBACK AND SUPPORT API ROUTES
# =============================================================================

@api_route('/feedback', methods=['POST'])
def submit_feedback():
    """Submit user feedback/suggestion"""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    feedback_type = data.get('type', 'suggestion').strip()
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    try:
        with get_db_cursor() as cur:
            cur.execute('''
                INSERT INTO feedback (name, email, feedback_type, message)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            ''', (name or None, email or None, feedback_type, message))
            result = cur.fetchone()
            feedback_id = result[0] if result else None
        
        try:
            notify_feedback({
                'name': name, 'email': email,
                'type': feedback_type, 'message': message
            })
        except Exception as notify_err:
            app_logger.warning(f"Failed to send feedback notification: {notify_err}")
        
        return jsonify({'success': True, 'id': feedback_id})
    except Exception as e:
        app_logger.error(f"Failed to submit feedback: {e}")
        return jsonify({'error': str(e)}), 500


@api_route('/features/weights', methods=['GET'])
def get_feature_weights():
    """Get current feature weights"""
    return jsonify(feature_extractor.get_weights())

@api_route('/features/weights', methods=['POST'])
def update_feature_weights():
    """Update feature weights (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    success = feature_extractor.set_weights(data)
    
    if success:
        return jsonify({'success': True, 'weights': feature_extractor.get_weights()})
    else:
        return jsonify({'error': 'Failed to save weights'}), 500

@api_route('/features/toggle', methods=['POST'])
def toggle_feature():
    """Toggle a feature on/off (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    feature = data.get('feature')
    enabled = data.get('enabled', True)
    
    if not feature:
        return jsonify({'error': 'Feature name required'}), 400
    
    weights = feature_extractor.get_weights()
    enabled_features = weights.get('enabled_features', ['lemma'])
    
    if enabled and feature not in enabled_features:
        enabled_features.append(feature)
    elif not enabled and feature in enabled_features:
        enabled_features.remove(feature)
    
    weights['enabled_features'] = enabled_features
    success = feature_extractor.set_weights(weights)
    
    if success:
        return jsonify({'success': True, 'enabled_features': enabled_features})
    else:
        return jsonify({'error': 'Failed to save'}), 500


def create_app():
    """Return app for scripts that need app context (e.g. import_connections)."""
    return app


if __name__ == "__main__":
    app_logger.info("Starting Tesserae V6 development server...")
    debug_mode = os.environ.get("TESSERAE_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)  # nosec B104
