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
import time
import threading
from collections import defaultdict
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
from backend.utils import (
    get_text_metadata, build_text_hierarchy, clean_cts_reference, resolve_text_path
)
from backend.cache import (
    get_cached_results, save_cached_results, 
    get_cache_stats, clear_cache
)
from backend.frequency_cache import (
    get_corpus_frequencies, initialize_all_caches,
    recalculate_language_frequencies
)
from backend.bigram_frequency import initialize_bigram_caches
from backend.distance_filter import passes_distance_filter, is_prose_text as is_prose_text_unified
from backend.lemma_cache import (
    get_cached_units, save_cached_units, get_file_hash,
    rebuild_lemma_cache, get_cache_stats as get_lemma_cache_stats,
    clear_lemma_cache
)
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
CORS(app, supports_credentials=True)  # Enable cross-origin requests


def api_route(path, **kwargs):
    """Decorator for API routes that auto-prepends API_PREFIX.
    On Marvin (behind Apache), prefix is empty. On dev, prefix is /api."""
    full_path = f"{API_PREFIX}{path}" if path != "/" else API_PREFIX or "/"
    return app.route(full_path, **kwargs)


# Application configuration
app.secret_key = os.environ.get("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # Handle proxy headers
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching for development
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {'pool_pre_ping': True, "pool_recycle": 300}

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
if os.environ.get('DEPLOYMENT_ENV') == 'marvin':
    from backend.marvin_auth import init_marvin_auth, get_current_user_info
    init_marvin_auth(app)
else:
    from backend.replit_auth import init_auth, get_current_user_info
    init_auth(app)

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
        pass

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
            cur.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key VARCHAR(255) PRIMARY KEY,
                    value TEXT
                )
            ''')
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
                    city VARCHAR(100),
                    country VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cur.execute('''
                ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS city VARCHAR(100)
            ''')
            cur.execute('''
                ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS country VARCHAR(100)
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_search_logs_created_at ON search_logs(created_at)
            ''')
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_search_logs_language ON search_logs(language)
            ''')
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
from backend.blueprints.hapax import hapax_bp, init_hapax_blueprint
from backend.blueprints.batch import batch_bp, init_batch_blueprint
from backend.blueprints.api_docs import api_docs_bp
from backend.blueprints.fusion import fusion_bp, init_fusion_blueprint
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
app.register_blueprint(downloads_bp, url_prefix=API_PREFIX or None)
app.register_blueprint(hapax_bp, url_prefix=API_PREFIX or None)
app.register_blueprint(batch_bp, url_prefix=batch_prefix)
app.register_blueprint(api_docs_bp, url_prefix=API_PREFIX or None)
app.register_blueprint(fusion_bp, url_prefix=API_PREFIX or None)

app_logger.info(f"Blueprints registered (API_PREFIX='{API_PREFIX}', env={DEPLOYMENT_ENV})")


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
    """Handle 404 errors by serving the SPA for client-side routing"""
    api_path = f"{API_PREFIX}/" if API_PREFIX else "/api/"
    if request.path.startswith(api_path):
        return jsonify({'error': 'Not found'}), 404
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
    return jsonify({'user': user_info})

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
    from backend.replit_auth import update_user_orcid
    if update_user_orcid(current_user.id, orcid, orcid_name):
        return jsonify({'success': True, 'user': get_current_user_info()})
    return jsonify({'error': 'Failed to update ORCID'}), 500

@api_route('/auth/orcid/unlink', methods=['POST'])
def unlink_orcid():
    """Remove ORCID from user account"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not logged in'}), 401
    from backend.replit_auth import unlink_user_orcid
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


@api_route('/health')
def api_health():
    """API health check endpoint"""
    return jsonify({"status": "ok", "message": "Tesserae V6 is running"})


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
            "last_updated_raw": last_updated
        })
    except Exception as e:
        app_logger.error(f"Error getting version info: {e}")
        return jsonify({"version": "6.0", "last_updated": None})


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

@api_route('/texts')
def get_texts():
    language = request.args.get('language', 'la')
    lang_dir = os.path.join(TEXTS_DIR, language)
    
    if not os.path.exists(lang_dir):
        return jsonify([])
    
    texts = []
    for filename in sorted(os.listdir(lang_dir)):
        if filename.endswith('.tess'):
            metadata = get_text_metadata(os.path.join(lang_dir, filename))
            texts.append(metadata)
    
    texts.sort(key=lambda x: (x['author'], x['title']))
    
    return jsonify(texts)

@api_route('/authors')
def get_authors():
    language = request.args.get('language', 'la')
    lang_dir = os.path.join(TEXTS_DIR, language)
    
    if not os.path.exists(lang_dir):
        return jsonify([])
    
    authors = {}
    for filename in os.listdir(lang_dir):
        if filename.endswith('.tess'):
            metadata = get_text_metadata(os.path.join(lang_dir, filename))
            author = metadata['author']
            if author not in authors:
                authors[author] = []
            authors[author].append(metadata)
    
    result = []
    for author in sorted(authors.keys()):
        result.append({
            'name': author,
            'works': sorted(authors[author], key=lambda x: natural_sort_key(x['title']))
        })
    
    return jsonify(result)

@api_route('/author-dates')
def get_public_author_dates():
    """Get author dates for timeline visualization (public endpoint)"""
    return jsonify(AUTHOR_DATES)

@api_route('/texts/hierarchy')
def get_texts_hierarchy():
    """Get hierarchical text structure: Author -> Work -> Parts"""
    language = request.args.get('language', 'la')
    lang_dir = os.path.join(TEXTS_DIR, language)
    
    if not os.path.exists(lang_dir):
        return jsonify({'authors': []})
    
    texts = []
    for filename in os.listdir(lang_dir):
        if filename.endswith('.tess'):
            metadata = get_text_metadata(os.path.join(lang_dir, filename))
            texts.append(metadata)
    
    hierarchy = build_text_hierarchy(texts)
    
    result = []
    for author_key in sorted(hierarchy.keys()):
        author_data = hierarchy[author_key]
        works = []
        for work_key in sorted(author_data['works'].keys(), key=natural_sort_key):
            work_data = author_data['works'][work_key]
            works.append({
                'work_key': work_key,
                'work': work_data['work'],
                'whole_text': work_data['whole_text'],
                'parts': work_data['parts']
            })
        result.append({
            'author_key': author_key,
            'author': author_data['author'],
            'works': works
        })
    
    return jsonify({'authors': result})


# =============================================================================
# PROSE DETECTION HELPERS
# =============================================================================
# Prose detection delegated to unified detect_text_type() in utils.py via
# distance_filter.is_prose_text (imported as is_prose_text_unified at top).
# POETRY_MAX_DISTANCE / PROSE_MAX_DISTANCE kept here for app.py's own use.

POETRY_MAX_DISTANCE = 20
PROSE_MAX_DISTANCE = 4


def _normalize_latin_lemma(lem):
    """Normalize Latin u/v and i/j for lemma comparison."""
    return lem.replace('v', 'u').replace('j', 'i')


def _normalize_lemma(lem, language='la'):
    """Normalize a lemma for index lookup. Handles Latin u/v/j/i and Greek diacritics."""
    if language == 'grc':
        import unicodedata
        decomposed = unicodedata.normalize('NFD', lem)
        stripped = ''.join(c for c in decomposed if unicodedata.category(c) != 'Mn')
        return stripped.lower().replace('ς', 'σ')
    return _normalize_latin_lemma(lem)


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

@api_route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        source_id = data.get('source')
        target_id = data.get('target')
        language = data.get('language', 'la')
        settings = data.get('settings', {})
        if 'bigram_boost' in data:
            settings['bigram_boost'] = data['bigram_boost']
        
        if not source_id or not target_id:
            return jsonify({"error": "Please select both source and target texts"})
        
        source_path = resolve_text_path(TEXTS_DIR, language, source_id)
        target_path = resolve_text_path(TEXTS_DIR, language, target_id)
        
        if not source_path or not target_path:
            return jsonify({"error": "Text files not found"})
        
        settings['language'] = language
        
        # Apply prose-aware max_distance defaults if not explicitly set
        if 'max_distance' not in settings or settings.get('max_distance') == 999:
            if is_prose_text_unified(source_id) or is_prose_text_unified(target_id):
                settings['max_distance'] = PROSE_MAX_DISTANCE
            else:
                settings['max_distance'] = POETRY_MAX_DISTANCE
        
        cached_results, cached_meta = get_cached_results(
            source_id, target_id, language, settings
        )
        
        if cached_results is not None:
            max_results = settings.get('max_results', 0)
            display_results = cached_results[:max_results] if max_results > 0 else cached_results
            user_id = current_user.id if current_user and current_user.is_authenticated else None
            city, country = get_user_location()
            log_search('text_comparison', language, source_id, target_id, None, 
                      settings.get('match_type', 'lemma'), len(cached_results), True, user_id,
                      city, country)
            meta = cached_meta or {}
            return jsonify({
                "results": display_results,
                "total_matches": len(cached_results),
                "source_lines": meta.get('source_lines', 0),
                "target_lines": meta.get('target_lines', 0),
                "stoplist_size": meta.get('stoplist_size', 0),
                "cached": True
            })
        
        source_unit_type = settings.get('source_unit_type', 'line')
        target_unit_type = settings.get('target_unit_type', 'line')
        
        source_units = get_processed_units(source_id, language, source_unit_type, text_processor)
        target_units = get_processed_units(target_id, language, target_unit_type, text_processor)
        
        corpus_frequencies = None
        stoplist_basis = settings.get('stoplist_basis', 'source_target')
        if stoplist_basis == 'corpus':
            freq_data = get_corpus_frequencies(language, text_processor)
            if freq_data:
                corpus_frequencies = freq_data.get('frequencies', {})
        
        match_type = settings.get('match_type', 'lemma')
        
        if match_type == 'sound':
            matches, stoplist_size = matcher.find_sound_matches(
                source_units, target_units, settings
            )
        elif match_type == 'edit_distance':
            matches, stoplist_size = matcher.find_edit_distance_matches(
                source_units, target_units, settings
            )
        elif match_type == 'semantic':
            from backend.semantic_similarity import find_semantic_matches
            matches, stoplist_size = find_semantic_matches(
                source_units, target_units, settings
            )
        else:
            matches, stoplist_size = matcher.find_matches(
                source_units, target_units, settings, 
                corpus_frequencies=corpus_frequencies
            )
        
        scored_results = scorer.score_matches(matches, source_units, target_units, settings, source_id, target_id)
        
        scored_results.sort(key=lambda x: x['overall_score'], reverse=True)
        
        metadata = {
            'source_lines': len(source_units),
            'target_lines': len(target_units),
            'stoplist_size': stoplist_size
        }
        
        save_cached_results(source_id, target_id, language, settings, 
                          scored_results, metadata)
        
        max_results = settings.get('max_results', 0)
        display_results = scored_results[:max_results] if max_results > 0 else scored_results
        
        user_id = current_user.id if current_user and current_user.is_authenticated else None
        city, country = get_user_location()
        log_search('text_comparison', language, source_id, target_id, None,
                  settings.get('match_type', 'lemma'), len(scored_results), False, user_id,
                  city, country)
        
        return jsonify({
            "results": display_results,
            "total_matches": len(scored_results),
            "source_lines": len(source_units),
            "target_lines": len(target_units),
            "stoplist_size": stoplist_size,
            "cached": False
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)})

@api_route('/cache/stats')
def cache_stats():
    return jsonify(get_cache_stats())

@api_route('/cache/clear', methods=['POST'])
def cache_clear():
    count = clear_cache()
    return jsonify({"cleared": count})

@api_route('/stoplist', methods=['POST'])
def get_stoplist():
    """Get the computed stoplist for given texts and settings"""
    data = request.get_json() or {}
    source_id = data.get('source', '')
    target_id = data.get('target', '')
    language = data.get('language', 'la')
    stoplist_basis = data.get('stoplist_basis', 'source_target')
    stoplist_size = data.get('stoplist_size', 0)
    
    if stoplist_size == -1:
        return jsonify({'stopwords': [], 'count': 0})
    
    try:
        source_units = get_processed_units(source_id, language, 'line', text_processor)
        target_units = get_processed_units(target_id, language, 'line', text_processor)
        
        corpus_frequencies = None
        if stoplist_basis == 'corpus':
            freq_data = get_corpus_frequencies(language, text_processor)
            if freq_data:
                corpus_frequencies = freq_data.get('frequencies', {})
        
        if stoplist_size > 0:
            stopwords = matcher.build_stoplist_manual(source_units + target_units, stoplist_size, language)
        else:
            stopwords = matcher.build_stoplist(source_units, target_units, stoplist_basis, language, corpus_frequencies)
        
        return jsonify({
            'stopwords': sorted(list(stopwords)),
            'count': len(stopwords)
        })
    except Exception as e:
        return jsonify({'error': str(e), 'stopwords': []})

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

@api_route('/text/<path:text_id>')
def get_text_content(text_id):
    """Get the full content of a text file"""
    language = request.args.get('language', 'la')
    filepath = resolve_text_path(TEXTS_DIR, language, text_id)
    
    if not filepath:
        return jsonify({'error': 'Text not found'}), 404
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = []
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            ref = ''
            text = line
            if line.startswith('<') and '>' in line:
                end_tag = line.index('>')
                ref = line[1:end_tag].strip()
                text = line[end_tag+1:].strip()
            
            lines.append({'ref': ref, 'text': text})
        
        metadata = get_text_metadata(filepath)
        
        return jsonify({
            'id': text_id,
            'author': metadata.get('author', ''),
            'title': metadata.get('title', ''),
            'lines': lines,
            'line_count': len(lines)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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


@api_route('/frequencies/<language>')
def get_frequencies(language):
    """Get cached corpus frequencies for a language"""
    freq_data = get_corpus_frequencies(language, text_processor)
    if freq_data:
        return jsonify({
            'language': language,
            'total_lemmas': freq_data.get('total_lemmas', 0),
            'unique_lemmas': len(freq_data.get('frequencies', {})),
            'text_count': freq_data.get('text_count', 0),
            'last_updated': freq_data.get('last_updated'),
            'top_50': list(freq_data.get('frequencies', {}).items())[:50]
        })
    return jsonify({'error': 'No frequency data available'}), 404

@api_route('/frequencies/recalculate', methods=['POST'])
def recalculate_frequencies():
    """Recalculate corpus frequencies for a language"""
    data = request.get_json() or {}
    language = data.get('language', 'la')
    
    result = recalculate_language_frequencies(language, text_processor)
    if result:
        return jsonify({
            'success': True,
            'language': language,
            'unique_lemmas': len(result.get('frequencies', {})),
            'total_lemmas': result.get('total_lemmas', 0)
        })
    return jsonify({'error': 'Failed to recalculate frequencies'}), 500

@api_route('/texts/preview', methods=['POST'])
def preview_text():
    """Preview how text will be chunked into units"""
    data = request.get_json() or {}
    raw_text = data.get('text', '')
    language = data.get('language', 'la')
    author = data.get('author', 'unknown')
    work = data.get('work', 'untitled')
    
    lines = raw_text.strip().split('\n')
    units = []
    errors = []
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('<') and '>' in line:
            tag_end = line.index('>') + 1
            tag = line[:tag_end]
            text = line[tag_end:].strip()
            units.append({
                'line_num': i,
                'tag': tag,
                'text': text,
                'valid': True
            })
        else:
            auto_tag = f"<{author}.{work}.{len(units)+1}>"
            units.append({
                'line_num': i,
                'tag': auto_tag,
                'text': line,
                'valid': True,
                'auto_tagged': True
            })
    
    return jsonify({
        'units': units,
        'total_lines': len(units),
        'errors': errors
    })

@api_route('/texts/add', methods=['POST'])
def add_text():
    """Add a new text to the corpus"""
    data = request.get_json() or {}
    language = data.get('language', 'la')
    author = data.get('author', '').strip()
    work = data.get('work', '').strip()
    content = data.get('content', '')
    
    if not author or not work:
        return jsonify({'error': 'Author and work title are required'}), 400
    
    if not content.strip():
        return jsonify({'error': 'Text content is required'}), 400
    
    safe_author = ''.join(c if c.isalnum() or c in '._-' else '_' for c in author.lower())
    safe_work = ''.join(c if c.isalnum() or c in '._-' else '_' for c in work.lower())
    filename = f"{safe_author}.{safe_work}.tess"
    
    lang_dir = os.path.join(TEXTS_DIR, language)
    os.makedirs(lang_dir, exist_ok=True)
    
    filepath = os.path.join(lang_dir, filename)
    
    if os.path.exists(filepath):
        return jsonify({'error': f'Text "{author} - {work}" already exists'}), 409
    
    lines = content.strip().split('\n')
    formatted_lines = []
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('<') and '>' in line:
            formatted_lines.append(line)
        else:
            tag = f"<{safe_author}.{safe_work}.{i}>"
            formatted_lines.append(f"{tag} {line}")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(formatted_lines))
    
    app_logger.info(f"Recalculating {language} corpus frequencies after adding {filename}...")
    recalculate_language_frequencies(language, text_processor)
    
    return jsonify({
        'success': True,
        'filename': filename,
        'language': language,
        'lines': len(formatted_lines)
    })


# =============================================================================
# LINE SEARCH (CORPUS-WIDE) API ROUTES
# =============================================================================
# These routes enable searching for words/phrases across the entire corpus
# using the pre-built inverted index for fast lookups.

@api_route('/line-search', methods=['POST'])
def line_search():
    """
    Search for words/phrases across the corpus with optional filters.
    Uses inverted index for fast lookups when available.
    """
    try:
        from backend.inverted_index import is_index_available, find_co_occurring_lemmas, has_lines_data, get_lines_batch
        from backend.distance_filter import passes_distance_filter, is_prose_text as is_prose_text_unified
        
        data = request.get_json() or {}
        
        query = data.get('query', '')
        language = data.get('language', 'la')
        search_type = data.get('search_type', 'lemma')
        author_filter = data.get('author', '')
        work_filter = data.get('work', '')
        line_start = data.get('line_start')
        line_end = data.get('line_end')
        max_results = data.get('max_results', 500)
        
        # Source exclusion - don't include the source line in results
        exclude_text_id = data.get('exclude_text_id', '')
        exclude_locus = data.get('exclude_locus', '')
        
        line_text = data.get('line_text', '')
        
        if query:
            import time as time_module
            search_start_time = time_module.time()
            
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
            else:
                stopwords = set(DEFAULT_ENGLISH_STOP_WORDS)
            
            # Optionally add top N corpus-frequent lemmas
            stoplist_size = data.get('stoplist_size', 10)
            corpus_freq_data = get_corpus_frequencies(language, text_processor)
            corpus_frequencies = corpus_freq_data.get('frequencies', {}) if corpus_freq_data else {}
            if stoplist_size > 0 and corpus_frequencies:
                sorted_lemmas = sorted(corpus_frequencies.items(), key=lambda x: x[1], reverse=True)
                stopwords.update(lemma for lemma, _ in sorted_lemmas[:stoplist_size])
            
            query_lemmas = set()
            if search_type == 'lemma':
                query_tokens = query.lower().split()
                for token in query_tokens:
                    lemmas = text_processor.lemmatize_word(token, language)
                    query_lemmas.update(_normalize_lemma(l, language) for l in lemmas)
                if not query_lemmas:
                    query_lemmas = set(_normalize_lemma(t, language) for t in query_tokens)
            else:
                query_lemmas = set(_normalize_lemma(t, language) for t in query.lower().split())
            
            # Filter out stopwords from query lemmas (like pairwise search)
            filtered_query_lemmas = query_lemmas - stopwords
            if len(filtered_query_lemmas) < 2:
                filtered_query_lemmas = query_lemmas  # fallback if too few remain
            
            results = []
            seen_results = set()
            
            # FAST PATH: Use inverted index if available (O(1) lookup vs O(n) scan)
            if search_type == 'lemma' and is_index_available(language) and len(filtered_query_lemmas) >= 2:
                candidates = find_co_occurring_lemmas(list(filtered_query_lemmas), language, min_matches=2)
                use_indexed_lines = has_lines_data(language)
                
                # Group candidates by text
                text_candidates = {}
                for filename, ref, matching_lemmas, positions in candidates:
                    if filename not in text_candidates:
                        text_candidates[filename] = []
                    text_candidates[filename].append((ref, matching_lemmas, positions))
                
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
                    year = author_info.get('year', 9999)
                    
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
                            pass
                    
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
                        
                        # Extract locus (last part of ref, clean CTS URNs)
                        locus_parts = ref.split() if ref else []
                        locus = locus_parts[-1] if locus_parts else ref
                        locus = clean_cts_reference(locus)
                        
                        # Find matched words in text using pre-indexed lemmas
                        matched_words = []
                        indexed_lemmas = set(line_info.get('lemmas', [])) if line_info else set()
                        indexed_tokens = line_info.get('tokens', []) if line_info else []
                        
                        # Use indexed data if available, otherwise fallback to quick token matching
                        if indexed_lemmas:
                            # Match query lemmas against indexed lemmas
                            matching_query_lemmas = indexed_lemmas & filtered_query_lemmas
                            if matching_query_lemmas:
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
                        
                        if len(set(matched_words)) < 2:
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
                            'matched_words': matched_words
                        })
                        
                        if len(results) >= max_results:
                            break
                    
                    if len(results) >= max_results:
                        break
            
            else:
                # SLOW PATH: Fallback to file scanning (for exact/regex search)
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
                    year = author_info.get('year', 9999)
                    
                    with open(filepath, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if not line or not line.startswith('<'):
                                continue
                            
                            try:
                                end_tag = line.index('>')
                                full_locus = line[1:end_tag].strip()
                                text = line[end_tag+1:].strip()
                                locus_parts = full_locus.split()
                                locus = locus_parts[-1] if locus_parts else full_locus
                                locus = clean_cts_reference(locus)
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
                                if query.lower() in text.lower():
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
                                else:
                                    for word in query.lower().split():
                                        if word in text.lower() and word not in stopwords:
                                            matched_words.append(word)
                                            matched_lemmas.add(word)
                                
                                # Skip results with fewer than 2 unique matching lemmas (like pairwise search)
                                if len(matched_lemmas) < 2:
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
                                    'matched_words': matched_words
                                })
                                
                                if len(results) >= max_results:
                                    break
                    
                    if len(results) >= max_results:
                        break
            
            # Sort results: first by era (chronological), then by year, then alphabetically by author
            era_order = {
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
            return jsonify({
                'results': results,
                'total': len(results),
                'query': query,
                'search_time': search_time
            })
        
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
        city, country = get_user_location()
        log_search('line_search', language, source_text_id, None, line_text,
                  match_type, len(all_results), False, user_id, city, country)
        
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
        
        if not lemmas or len(lemmas) < 1:
            return jsonify({'error': 'At least 1 lemma required'}), 400
        
        lang_dates = AUTHOR_DATES.get(language, {})
        
        if not is_index_available(language):
            return jsonify({'error': 'Index not available for this language'}), 400

        # Normalize lemmas for index lookup (strip Greek diacritics, Latin u/v)
        normalized_lemmas = [_normalize_lemma(l, language) for l in lemmas]
        matches = find_co_occurring_lemmas(normalized_lemmas, language, min_matches=min(2, len(normalized_lemmas)))
        
        results = []
        text_matches = {}
        text_genre_cache = {}
        
        for filename, ref, matching_lemmas, positions in matches:
            if filename in exclude_texts:
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
                    pass
            
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
                
                results.append({
                    'text_id': filename,
                    'author': metadata['author'],
                    'title': metadata['title'],
                    'locus': ref,
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
                    except:
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

    # Only author and work are required
    if not author or not work:
        return jsonify({'error': 'Author and work title are required'}), 400
    if language not in allowed_languages:
        return jsonify({'error': 'Please select a valid language (Latin, Greek, or English)'}), 400
    
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

@api_route('/admin/login', methods=['POST'])
def admin_login():
    """Verify admin password"""
    # Legacy admin login brute-force protection (process-local).
    if not hasattr(admin_login, '_attempts'):
        admin_login._attempts = defaultdict(list)      # key -> [timestamps]
        admin_login._lockouts = {}                     # key -> lockout_until_epoch
        admin_login._lock = threading.Lock()

    max_attempts = int(os.environ.get('ADMIN_LOGIN_MAX_ATTEMPTS', '5'))
    window_seconds = int(os.environ.get('ADMIN_LOGIN_WINDOW_SECONDS', '900'))
    lockout_seconds = int(os.environ.get('ADMIN_LOGIN_LOCKOUT_SECONDS', '900'))

    def _client_ip():
        forwarded_for = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
        return forwarded_for or request.remote_addr or 'unknown'

    def _keys(email):
        normalized_email = (email or '').strip().lower() or 'unknown'
        ip = _client_ip()
        return [f"ip:{ip}", f"email:{normalized_email}", f"combo:{ip}|{normalized_email}"]

    def _prune(now):
        cutoff = now - window_seconds
        for k, ts_list in list(admin_login._attempts.items()):
            recent = [ts for ts in ts_list if ts >= cutoff]
            if recent:
                admin_login._attempts[k] = recent
            else:
                admin_login._attempts.pop(k, None)
        for k, until in list(admin_login._lockouts.items()):
            if until <= now:
                admin_login._lockouts.pop(k, None)

    data = request.get_json() or {}
    password = data.get('password', '')
    email = (data.get('email') or data.get('username') or '').strip().lower()

    with admin_login._lock:
        now = time.time()
        _prune(now)
        retry_after = [max(0, int(admin_login._lockouts[k] - now)) for k in _keys(email) if k in admin_login._lockouts]
        if retry_after:
            return (
                jsonify({'error': 'Too many login attempts. Please try again later.'}),
                429,
                {'Retry-After': str(max(retry_after))}
            )
    
    if not ADMIN_PASSWORD:
        return jsonify({'error': 'Admin password not configured'}), 500
    
    if password == ADMIN_PASSWORD:
        with admin_login._lock:
            for k in _keys(email):
                admin_login._attempts.pop(k, None)
                admin_login._lockouts.pop(k, None)
        return jsonify({'success': True})
    else:
        with admin_login._lock:
            now = time.time()
            _prune(now)
            for k in _keys(email):
                attempts = admin_login._attempts[k]
                attempts.append(now)
                if len(attempts) >= max_attempts:
                    admin_login._lockouts[k] = now + lockout_seconds
        return jsonify({'error': 'Invalid password'}), 401

@api_route('/admin/author-dates', methods=['GET'])
def get_author_dates():
    """Get all author dates (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    return jsonify(AUTHOR_DATES)

@api_route('/admin/author-dates/<language>/<author_key>', methods=['PUT'])
def update_author_date(language, author_key):
    """Update or add an author date entry (admin only)"""
    global AUTHOR_DATES
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    year = data.get('year')
    era = data.get('era', 'Unknown')
    note = data.get('note', '')
    
    if language not in AUTHOR_DATES:
        AUTHOR_DATES[language] = {}
    
    AUTHOR_DATES[language][author_key] = {
        'year': int(year) if year is not None and year != '' else None,
        'era': era,
        'note': note
    }
    
    with open(author_dates_path, 'w') as f:
        json.dump(AUTHOR_DATES, f, indent=2)
    
    return jsonify({'success': True})

@api_route('/admin/author-dates/<language>/<author_key>', methods=['DELETE'])
def delete_author_date(language, author_key):
    """Delete an author date entry (admin only)"""
    global AUTHOR_DATES
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if language in AUTHOR_DATES and author_key in AUTHOR_DATES[language]:
        del AUTHOR_DATES[language][author_key]
        with open(author_dates_path, 'w') as f:
            json.dump(AUTHOR_DATES, f, indent=2)
        return jsonify({'success': True})
    
    return jsonify({'error': 'Entry not found'}), 404

@api_route('/admin/lemma-cache/stats', methods=['GET'])
def lemma_cache_stats():
    """Get lemma cache statistics (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    return jsonify(get_lemma_cache_stats())

@api_route('/admin/lemma-cache/rebuild', methods=['POST'])
def rebuild_lemma_cache_endpoint():
    """Rebuild lemma cache for a language (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    language = data.get('language', 'la')
    
    global processed_cache
    processed_cache = {}
    
    result = rebuild_lemma_cache(language, text_processor)
    return jsonify(result)

@api_route('/admin/lemma-cache/clear', methods=['POST'])
def clear_lemma_cache_endpoint():
    """Clear lemma cache (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    language = data.get('language')
    
    global processed_cache
    processed_cache = {}
    
    result = clear_lemma_cache(language)
    return jsonify(result)

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

@api_route('/admin/feedback', methods=['GET'])
def get_feedback():
    """Get all feedback submissions (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute('''
                SELECT id, name, email, feedback_type, message, status, created_at, admin_notes, responded_by, responded_at
                FROM feedback
                ORDER BY created_at DESC
            ''')
            rows = cur.fetchall()
        
        feedback_list = []
        for row in rows:
            feedback_list.append({
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'type': row[3],
                'message': row[4],
                'status': row[5] or 'pending',
                'created_at': row[6].isoformat() if row[6] else None,
                'admin_notes': row[7],
                'responded_by': row[8],
                'responded_at': row[9].isoformat() if row[9] else None
            })
        return jsonify(feedback_list)
    except Exception as e:
        app_logger.error(f"Failed to get feedback: {e}")
        return jsonify({'error': str(e)}), 500

@api_route('/admin/feedback/<int:feedback_id>', methods=['PUT'])
def update_feedback(feedback_id):
    """Update feedback status (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    status = data.get('status')
    if status:
        status = status.strip().lower()
        if status in ('new', 'open'):
            status = 'pending'
        elif status in ('resolved', 'done', 'closed'):
            status = 'responded'
        elif status not in ('pending', 'in_progress', 'responded'):
            return jsonify({'error': 'Invalid status'}), 400
    admin_notes = data.get('admin_notes')
    
    try:
        with get_db_cursor() as cur:
            if status and admin_notes is not None:
                if status == 'responded':
                    cur.execute(
                        '''
                        UPDATE feedback
                        SET status = %s, admin_notes = %s, responded_by = %s, responded_at = %s
                        WHERE id = %s
                        ''',
                        (status, admin_notes, 'admin', datetime.now(), feedback_id),
                    )
                elif status == 'pending':
                    cur.execute(
                        '''
                        UPDATE feedback
                        SET status = %s, admin_notes = %s, responded_by = NULL, responded_at = NULL
                        WHERE id = %s
                        ''',
                        (status, admin_notes, feedback_id),
                    )
                else:
                    cur.execute('UPDATE feedback SET status = %s, admin_notes = %s WHERE id = %s', (status, admin_notes, feedback_id))
            elif status:
                if status == 'responded':
                    cur.execute(
                        '''
                        UPDATE feedback
                        SET status = %s, responded_by = %s, responded_at = %s
                        WHERE id = %s
                        ''',
                        (status, 'admin', datetime.now(), feedback_id),
                    )
                elif status == 'pending':
                    cur.execute(
                        '''
                        UPDATE feedback
                        SET status = %s, responded_by = NULL, responded_at = NULL
                        WHERE id = %s
                        ''',
                        (status, feedback_id),
                    )
                else:
                    cur.execute('UPDATE feedback SET status = %s WHERE id = %s', (status, feedback_id))
            elif admin_notes is not None:
                cur.execute('UPDATE feedback SET admin_notes = %s WHERE id = %s', (admin_notes, feedback_id))
        return jsonify({'success': True})
    except Exception as e:
        app_logger.error(f"Failed to update feedback: {e}")
        return jsonify({'error': str(e)}), 500

@api_route('/admin/settings', methods=['GET'])
def get_settings():
    """Get admin settings (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute('SELECT key, value FROM settings')
            rows = cur.fetchall()
        
        settings = {row[0]: row[1] for row in rows}
        return jsonify(settings)
    except Exception as e:
        app_logger.error(f"Failed to get settings: {e}")
        return jsonify({'error': str(e)}), 500

@api_route('/admin/settings', methods=['POST'])
def update_settings():
    """Update admin settings (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    
    try:
        with get_db_cursor() as cur:
            for key, value in data.items():
                cur.execute('''
                    INSERT INTO settings (key, value) VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                ''', (key, value))
        return jsonify({'success': True})
    except Exception as e:
        app_logger.error(f"Failed to update settings: {e}")
        return jsonify({'error': str(e)}), 500

@api_route('/admin/user-data', methods=['GET'])
def get_user_data():
    """Get all data for a user by email (GDPR data export)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    email = request.args.get('email', '').strip().lower()
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    try:
        from backend.models import User, SavedSearch
        result = {'email': email, 'found': False}
        
        user = User.query.filter(User.email.ilike(email)).first()
        if user:
            result['found'] = True
            result['profile'] = {
                'id': user.id,
                'replit_id': user.replit_id,
                'name': user.name,
                'email': user.email,
                'profile_image': user.profile_image,
                'institution': user.institution,
                'created_at': str(user.created_at) if user.created_at else None
            }
            
            saved = SavedSearch.query.filter_by(user_id=user.id).all()
            result['saved_searches'] = [{
                'id': s.id,
                'name': s.name,
                'created_at': str(s.created_at) if s.created_at else None,
                'settings': s.settings
            } for s in saved]
            
            with get_db_cursor(commit=False) as cur:
                cur.execute('SELECT COUNT(*) FROM search_logs WHERE user_id = %s', (user.id,))
                count_row = cur.fetchone()
                result['search_logs'] = count_row[0] if count_row else 0
        
        with get_db_cursor(commit=False) as cur:
            cur.execute('SELECT id, name, feedback_type, message, status, created_at FROM feedback WHERE email ILIKE %s', (email,))
            feedback_rows = cur.fetchall()
            result['feedback'] = [{
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'message': row[3],
                'status': row[4],
                'created_at': str(row[5]) if row[5] else None
            } for row in feedback_rows]
            
            if feedback_rows and not result['found']:
                result['found'] = True
        
        return jsonify(result)
    except Exception as e:
        app_logger.error(f"Failed to get user data: {e}")
        return jsonify({'error': str(e)}), 500

@api_route('/admin/analytics', methods=['GET'])
def get_analytics():
    """Get search analytics (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db_cursor(commit=False) as cur:
            # Total searches
            cur.execute('SELECT COUNT(*) FROM search_logs')
            row = cur.fetchone()
            total_searches = row[0] if row else 0
            
            # Searches by type
            cur.execute('''
                SELECT search_type, COUNT(*) as count 
                FROM search_logs 
                GROUP BY search_type 
                ORDER BY count DESC
            ''')
            by_type = [{'type': row[0], 'count': row[1]} for row in cur.fetchall()]
            
            # Searches by language
            cur.execute('''
                SELECT language, COUNT(*) as count 
                FROM search_logs 
                GROUP BY language 
                ORDER BY count DESC
            ''')
            by_language = [{'language': row[0], 'count': row[1]} for row in cur.fetchall()]
            
            # Searches per day (last 30 days)
            cur.execute('''
                SELECT DATE(created_at) as day, COUNT(*) as count 
                FROM search_logs 
                WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY DATE(created_at) 
                ORDER BY day DESC
            ''')
            per_day = [{'date': str(row[0]), 'count': row[1]} for row in cur.fetchall()]
            
            # Top source texts
            cur.execute('''
                SELECT source_text, COUNT(*) as count 
                FROM search_logs 
                WHERE source_text IS NOT NULL
                GROUP BY source_text 
                ORDER BY count DESC 
                LIMIT 10
            ''')
            top_sources = [{'text': row[0], 'count': row[1]} for row in cur.fetchall()]
            
            # Top target texts
            cur.execute('''
                SELECT target_text, COUNT(*) as count 
                FROM search_logs 
                WHERE target_text IS NOT NULL
                GROUP BY target_text 
                ORDER BY count DESC 
                LIMIT 10
            ''')
            top_targets = [{'text': row[0], 'count': row[1]} for row in cur.fetchall()]
            
            # Recent line search queries
            cur.execute('''
                SELECT query_text, language, created_at 
                FROM search_logs 
                WHERE search_type = 'line_search' AND query_text IS NOT NULL
                ORDER BY created_at DESC 
                LIMIT 20
            ''')
            recent_queries = [{'query': row[0], 'language': row[1], 'date': str(row[2])} 
                             for row in cur.fetchall()]
            
            # Match type usage
            cur.execute('''
                SELECT match_type, COUNT(*) as count 
                FROM search_logs 
                WHERE match_type IS NOT NULL
                GROUP BY match_type 
                ORDER BY count DESC
            ''')
            by_match_type = [{'type': row[0], 'count': row[1]} for row in cur.fetchall()]
            
            # Cached vs non-cached
            cur.execute('''
                SELECT cached, COUNT(*) as count 
                FROM search_logs 
                GROUP BY cached
            ''')
            cache_stats = {row[0]: row[1] for row in cur.fetchall()}
            
            # Unique users (logged in)
            cur.execute('''
                SELECT COUNT(DISTINCT user_id) 
                FROM search_logs 
                WHERE user_id IS NOT NULL
            ''')
            row = cur.fetchone()
            unique_users = row[0] if row else 0
            
            # Searches today
            cur.execute('''
                SELECT COUNT(*) 
                FROM search_logs 
                WHERE DATE(created_at) = CURRENT_DATE
            ''')
            row = cur.fetchone()
            searches_today = row[0] if row else 0
            
            # Top countries
            cur.execute('''
                SELECT country, COUNT(*) as count 
                FROM search_logs 
                WHERE country IS NOT NULL
                GROUP BY country 
                ORDER BY count DESC 
                LIMIT 15
            ''')
            top_countries = [{'country': row[0], 'count': row[1]} for row in cur.fetchall()]
            
            # Top cities
            cur.execute('''
                SELECT city, country, COUNT(*) as count 
                FROM search_logs 
                WHERE city IS NOT NULL
                GROUP BY city, country 
                ORDER BY count DESC 
                LIMIT 20
            ''')
            top_cities = [{'city': row[0], 'country': row[1], 'count': row[2]} for row in cur.fetchall()]
        
        return jsonify({
            'total_searches': total_searches,
            'searches_today': searches_today,
            'unique_users': unique_users,
            'by_type': by_type,
            'by_language': by_language,
            'by_match_type': by_match_type,
            'per_day': per_day,
            'top_sources': top_sources,
            'top_targets': top_targets,
            'recent_queries': recent_queries,
            'cache_hits': cache_stats.get(True, 0),
            'cache_misses': cache_stats.get(False, 0),
            'top_countries': top_countries,
            'top_cities': top_cities
        })
    except Exception as e:
        app_logger.error(f"Failed to get analytics: {e}")
        return jsonify({'error': str(e)}), 500


def create_app():
    """Return app for scripts that need app context (e.g. import_connections)."""
    return app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
