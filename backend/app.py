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
from datetime import datetime

# Application modules
from backend.logging_config import setup_logging, get_logger
from backend.db_utils import DatabaseError, get_db_cursor
from backend.services import get_client_ip, get_user_location, log_search

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
from backend.utils import get_text_metadata, build_text_hierarchy, clean_cts_reference
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

# Create Flask app with static file serving
app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path='')
CORS(app, supports_credentials=True)  # Enable cross-origin requests

# Application configuration
app.secret_key = os.environ.get("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # Handle proxy headers
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching for development
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {'pool_pre_ping': True, "pool_recycle": 300}

# =============================================================================
# ENVIRONMENT-BASED ROUTE PREFIX
# =============================================================================
# On Marvin (Apache+WSGI), the /api prefix is handled by Apache's WSGIScriptAlias,
# so Flask routes should NOT include /api. On Replit, Flask handles everything
# directly, so routes need the /api prefix.
# Set DEPLOYMENT_ENV=marvin in .env on Marvin server to use empty prefix.
DEPLOYMENT_ENV = os.environ.get("DEPLOYMENT_ENV", "replit")
API_PREFIX = "" if DEPLOYMENT_ENV == "marvin" else "/api"

def api_route(path, **kwargs):
    """Decorator factory for API routes that handles environment-based prefixes.
    
    Usage: @api_route('/health') instead of @api_route('/health')
    """
    full_path = f"{API_PREFIX}{path}" if path != "/" else API_PREFIX or "/"
    return app.route(full_path, **kwargs)

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
    print("Database tables initialized successfully")
except Exception as e:
    print(f"Warning: Could not initialize database tables: {e}")
    print("Database will be initialized on first request")

# =============================================================================
# AUTHENTICATION SETUP
# =============================================================================
DEPLOYMENT_ENV = os.environ.get('DEPLOYMENT_ENV', 'replit')
AUTH_TYPE = 'replit' if DEPLOYMENT_ENV == 'replit' else 'password'

if DEPLOYMENT_ENV == 'replit' and os.environ.get('REPL_ID'):
    from backend.replit_auth import init_auth, get_current_user_info
    init_auth(app)
    print("Replit authentication initialized")
elif DEPLOYMENT_ENV == 'marvin':
    from backend.marvin_auth import init_marvin_auth, get_current_user_info
    init_marvin_auth(app)
    print("Marvin password authentication initialized")
else:
    from backend.replit_auth import get_current_user_info
    print("Auth disabled - no REPL_ID in Replit mode")

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
    filepath = os.path.join(TEXTS_DIR, language, text_id)
    cache_key = f"{filepath}:{language}:{unit_type}"
    
    if cache_key in processed_cache:
        return processed_cache[cache_key]
    
    cached = get_cached_units(text_id, language)
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
        save_cached_units(text_id, language, units_line, units_phrase, file_hash)
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
    with open(author_dates_path, 'r') as f:
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
                    admin_notes TEXT
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
                    admin_notes TEXT
                )
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

# Register blueprints with environment-based URL prefix
# On Marvin: no prefix (Apache handles /api)
# On Replit: /api prefix added here
# Note: admin_bp has its own /admin prefix, so we combine them
admin_prefix = f"{API_PREFIX}/admin" if API_PREFIX else "/admin"
app.register_blueprint(admin_bp, url_prefix=admin_prefix)
app.register_blueprint(search_bp, url_prefix=API_PREFIX or None)
app.register_blueprint(corpus_bp, url_prefix=API_PREFIX or None)
app.register_blueprint(intertext_bp, url_prefix=API_PREFIX or None)
app.register_blueprint(downloads_bp, url_prefix=API_PREFIX or None)
app.register_blueprint(hapax_bp, url_prefix=API_PREFIX or None)
app.register_blueprint(batch_bp, url_prefix=API_PREFIX or None)
app.register_blueprint(api_docs_bp, url_prefix=API_PREFIX or None)

app_logger.info("Blueprints registered.")


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

@app.route('/legacy')
def legacy_frontend():
    """Serve the legacy frontend for full feature access during migration"""
    legacy_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
    return send_from_directory(legacy_path, 'index.html')

@app.route('/static/downloads/<path:filename>')
def serve_downloads(filename):
    """Serve downloadable files from static/downloads/"""
    downloads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'downloads')
    return send_from_directory(downloads_path, filename)

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors by serving the SPA for client-side routing"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    static_folder = app.static_folder or '../frontend'
    return send_from_directory(static_folder, 'index.html')


# =============================================================================
# AUTHENTICATION API ROUTES
# =============================================================================

@api_route('/auth/user')
def get_auth_user():
    """Get current logged-in user info"""
    user_info = get_current_user_info()
    deployment_env = os.environ.get('DEPLOYMENT_ENV', 'replit')
    if deployment_env == 'replit':
        auth_enabled = bool(os.environ.get('REPL_ID'))
        auth_type = 'replit'
    else:
        auth_enabled = True
        auth_type = 'password'
    return jsonify({'user': user_info, 'auth_enabled': auth_enabled, 'auth_type': auth_type})

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
        
        lang_dir = os.path.join(TEXTS_DIR, language)
        source_path = os.path.join(lang_dir, source_id)
        target_path = os.path.join(lang_dir, target_id)
        
        if not os.path.exists(source_path) or not os.path.exists(target_path):
            return jsonify({"error": "Text files not found"})
        
        settings['language'] = language
        
        # Apply prose-aware max_distance defaults if not explicitly set
        # Use inline prose detection (faster and more reliable)
        if 'max_distance' not in settings or settings.get('max_distance') == 999:
            PROSE_AUTHORS = ['cicero', 'caesar', 'livy', 'sallust', 'tacitus', 'suetonius',
                            'nepos', 'quintilian', 'pliny', 'apuleius', 'petronius',
                            'augustine', 'jerome', 'ambrose', 'seneca_prose',
                            'cic.', 'caes.', 'liv.', 'sall.', 'tac.', 'suet.', 'nep.',
                            'quint.', 'plin.', 'apul.', 'petron.', 'aug.', 'hier.', 'ambr.']
            PROSE_MARKERS = ['epistulae', 'letters', 'de_officiis', 'de_oratore', 
                            'de_finibus', 'de_natura', 'tusculan', 'bellum_gallicum',
                            'historiae', 'annales', 'agricola', 'germania', 'dialogus',
                            'satyricon', 'confessions', 'de_civitate']
            
            source_lower = source_id.lower()
            target_lower = target_id.lower()
            source_is_prose = any(marker in source_lower for marker in PROSE_AUTHORS + PROSE_MARKERS)
            target_is_prose = any(marker in target_lower for marker in PROSE_AUTHORS + PROSE_MARKERS)
            
            # Use prose settings if either text is prose
            if source_is_prose or target_is_prose:
                settings['max_distance'] = 4  # Very tight for compact prose phrases
            else:
                settings['max_distance'] = 20  # Poetry allows more spread
        
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
    lang_dir = os.path.join(TEXTS_DIR, language)
    filepath = os.path.join(lang_dir, text_id)
    
    if not os.path.exists(filepath):
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
            lang_dir = os.path.join(TEXTS_DIR, lang)
            filepath = os.path.join(lang_dir, text_id)
            if os.path.exists(filepath):
                language = lang
                break
    
    lang_dir = os.path.join(TEXTS_DIR, language) if language else TEXTS_DIR
    filepath = os.path.join(lang_dir, text_id)
    
    if not os.path.exists(filepath):
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
        import re
        
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
            
            def normalize_latin_lemma(lemma):
                """Normalize Latin lemmas to match index (v->u, j->i)"""
                if language == 'la':
                    return lemma.replace('v', 'u').replace('j', 'i')
                return lemma
            
            query_lemmas = set()
            if search_type == 'lemma':
                query_tokens = query.lower().split()
                for token in query_tokens:
                    lemmas = text_processor.lemmatize_word(token, language)
                    query_lemmas.update(normalize_latin_lemma(l) for l in lemmas)
                if not query_lemmas:
                    query_lemmas = set(normalize_latin_lemma(t) for t in query_tokens)
            else:
                query_lemmas = set(normalize_latin_lemma(t) for t in query.lower().split())
            
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
                    filepath = os.path.join(lang_dir, filename)
                    if not os.path.exists(filepath):
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
                x.get('year', 9999),  # Sort by year within era
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
            lang_dir = os.path.join(TEXTS_DIR, language)
            source_path = os.path.join(lang_dir, source_text_id)
            if os.path.exists(source_path):
                with open(source_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('<') and '>' in line:
                            end_tag = line.index('>')
                            ref = line[1:end_tag].strip()
                            if ref == line_ref:
                                line_text = line[end_tag+1:].strip()
                                break
        
        if not line_text:
            return jsonify({'error': 'Could not find the specified line'}), 404
        
        source_unit = text_processor.process_line(line_text, language)
        source_lemmas = set(source_unit.get('lemmas', []))
        
        if len(source_lemmas) < 1:
            return jsonify({'error': 'No lemmas found in the line'}), 400
        
        # Extract key phrases for exact phrase matching
        # Normalize query: lowercase, strip punctuation for matching
        import re
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
        
        # USE SAME STOPLIST AS PAIRWISE SEARCH: Default stopwords + Zipf elbow detection
        # This uses matcher.py logic with DEFAULT_LATIN_STOP_WORDS (70+ words)
        from backend.matcher import DEFAULT_LATIN_STOP_WORDS, DEFAULT_GREEK_STOP_WORDS, DEFAULT_ENGLISH_STOP_WORDS
        from backend.zipf import find_zipf_elbow
        from collections import Counter
        
        # Get base stopwords for language (same as pairwise)
        if language == 'la':
            stopwords = set(DEFAULT_LATIN_STOP_WORDS)
        elif language == 'grc':
            stopwords = set(DEFAULT_GREEK_STOP_WORDS)
        else:
            stopwords = set(DEFAULT_ENGLISH_STOP_WORDS)
        
        # Add Zipf-detected stopwords from corpus frequencies (same as pairwise)
        if corpus_frequencies:
            freq_counter = Counter(corpus_frequencies)
            zipf_stops = find_zipf_elbow(freq_counter, min_stopwords=10, max_stopwords=50)
            stopwords = stopwords.union(zipf_stops)
        
        # Filter source lemmas to exclude stopwords AND short words (same as Matcher)
        # Matcher uses len(lemma) > 2 filter
        filtered_source_lemmas = {l for l in source_lemmas if l not in stopwords and len(l) > 2}
        if len(filtered_source_lemmas) < min_matches:
            # Fallback: include longer stopwords if too few content words
            filtered_source_lemmas = {l for l in source_lemmas if len(l) > 2}
        
        all_results = []
        texts_searched = 0
        seen_results = set()
        
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
                    
                author_key = filename.split('.')[0].lower()
                author_info = lang_dates.get(author_key, {})
                author_year = author_info.get('year')
                author_era = author_info.get('era', 'Unknown')
                
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
                    if not unit:
                        continue
                    
                    result_key = (filename, ref)
                    if result_key in seen_results:
                        continue
                    seen_results.add(result_key)
                    
                    target_text = unit.get('text', '').lower().strip()
                    query_text = line_text.lower().strip()
                    
                    # EXCLUDE the exact source line (same text + same reference)
                    if filename == source_text_id and ref == line_ref:
                        continue
                    
                    # EXCLUDE lines with identical text (duplicate texts in corpus)
                    if target_text == query_text:
                        continue
                    
                    # Check for PHRASE matches (key to finding quotations!)
                    target_normalized = re.sub(r'[^\w\s]', '', target_text)
                    phrase_match_bonus = 1.0
                    matched_phrase = None
                    
                    # Check for key phrases from query in target
                    # Phrase matches get OVERWHELMING priority to surface quotations
                    for phrase in key_phrases:
                        if phrase in target_normalized:
                            # Much stronger bonus: 1000+ for any phrase match
                            phrase_match_bonus = 1000.0 + len(phrase) * 100
                            matched_phrase = phrase
                            break
                    
                    # CRITICAL: Verify matched lemmas actually exist in target line
                    # The index may return stale/mismatched data from duplicate refs
                    target_lemmas_list = unit.get('lemmas', [])
                    
                    # Normalize Latin u/v and i/j for comparison (cached may have 'vir', query has 'uir')
                    def normalize_latin_lemma(lem):
                        return lem.replace('v', 'u').replace('j', 'i')
                    
                    target_lemmas_normalized = {normalize_latin_lemma(l) for l in target_lemmas_list}
                    source_lemmas_normalized = {normalize_latin_lemma(l) for l in filtered_source_lemmas}
                    matching_lemmas_normalized = {normalize_latin_lemma(l) for l in matching_lemmas}
                    
                    # Intersect normalized lemmas
                    shared_normalized = matching_lemmas_normalized & target_lemmas_normalized & source_lemmas_normalized
                    if len(shared_normalized) < min_matches:
                        continue  # Skip if not enough verified matches
                    
                    # Use normalized shared set for display
                    shared = shared_normalized
                    
                    match_count = len(shared)
                    target_length = len(target_lemmas_list) if target_lemmas_list else len(unit.get('tokens', []))
                    
                    # Calculate positions from actual target lemmas (more reliable than index)
                    # Index positions may be stale for duplicate refs
                    match_positions = [i for i, lem in enumerate(target_lemmas_list) if normalize_latin_lemma(lem) in shared]
                    
                    # Calculate distance (span) between matched words - V3 style
                    if len(match_positions) >= 2:
                        distance = match_positions[-1] - match_positions[0] + 1
                    else:
                        distance = 1
                    
                    # APPLY MAX_DISTANCE FILTER (same as pairwise search)
                    # Poetry allows wider spans, prose requires tighter clustering
                    # Use inline prose detection (faster and more reliable than import)
                    PROSE_AUTHORS = ['cicero', 'caesar', 'livy', 'sallust', 'tacitus', 'suetonius',
                                    'nepos', 'quintilian', 'pliny', 'apuleius', 'petronius',
                                    'augustine', 'jerome', 'ambrose', 'seneca_prose',
                                    'cic.', 'caes.', 'liv.', 'sall.', 'tac.', 'suet.', 'nep.',
                                    'quint.', 'plin.', 'apul.', 'petron.', 'aug.', 'hier.', 'ambr.']
                    PROSE_MARKERS = ['epistulae', 'letters', 'de_officiis', 'de_oratore', 
                                    'de_finibus', 'de_natura', 'tusculan', 'bellum_gallicum',
                                    'historiae', 'annales', 'agricola', 'germania', 'dialogus',
                                    'satyricon', 'confessions', 'de_civitate']
                    
                    text_lower = filename.lower()
                    is_prose = any(marker in text_lower for marker in PROSE_AUTHORS + PROSE_MARKERS)
                    
                    POETRY_MAX_DISTANCE = 20
                    PROSE_MAX_DISTANCE = 4  # Very tight for compact prose phrases
                    max_dist = PROSE_MAX_DISTANCE if is_prose else POETRY_MAX_DISTANCE
                    
                    if distance > max_dist:
                        continue  # Skip results where matched words are too far apart
                    
                    # V3-STYLE SCORING: score = sum(IDF) / (1 + log(distance))
                    idf_sum = 0
                    for lemma in shared:
                        freq = corpus_frequencies.get(lemma, 1)
                        idf = math.log(total_corpus_words / (freq + 1)) + 1
                        idf_sum += idf
                    
                    # V3 distance penalty: 1 / (1 + log(distance))
                    distance_factor = 1.0 / (1 + math.log(distance + 1))
                    
                    # V3 final score: IDF sum * distance factor
                    score = idf_sum * distance_factor * phrase_match_bonus
                    tokens = unit.get('tokens', [])
                    
                    parts = filename.replace('.tess', '').split('.')
                    author_name = parts[0] if parts else ''
                    work_name = '.'.join(parts[1:]) if len(parts) > 1 else ''
                    
                    text_matches.append({
                        'text_id': filename,
                        'author': author_name,
                        'work': work_name,
                        'ref': ref,
                        'text': unit.get('text', ''),
                        'tokens': tokens,
                        'highlight_indices': match_positions,
                        'matched_lemmas': list(shared),
                        'match_count': match_count,
                        'score': round(score, 3),
                        'year': author_year,
                        'era': author_era
                    })
                
                text_matches.sort(key=lambda x: x['score'], reverse=True)
                all_results.extend(text_matches[:max_per_text])
        else:
            # FALLBACK: Scan all texts (original behavior)
            text_files = [f for f in os.listdir(lang_dir) if f.endswith('.tess')]
            if exclude_source and source_text_id:
                text_files = [f for f in text_files if f != source_text_id]
            
            for filename in text_files:
                texts_searched += 1
                filepath = os.path.join(lang_dir, filename)
                metadata = get_text_metadata(filepath)
                
                author_key = filename.split('.')[0].lower()
                author_info = lang_dates.get(author_key, {})
                author_year = author_info.get('year')
                author_era = author_info.get('era', 'Unknown')
                
                units = get_processed_units(filename, language, 'line', text_processor)
                
                text_matches = []
                
                for unit in units:
                    target_lemmas_list = unit.get('lemmas', [])
                    target_lemmas = set(target_lemmas_list)
                    target_length = len(target_lemmas_list)
                    
                    shared = filtered_source_lemmas & target_lemmas
                    match_count = len(shared)
                    
                    if match_count >= min_matches:
                        target_text = unit.get('text', '').lower().strip()
                        query_text = line_text.lower().strip()
                        unit_ref = unit.get('ref', '')
                        
                        # EXCLUDE the exact source line (same text + same reference)
                        if filename == source_text_id and unit_ref == line_ref:
                            continue
                        
                        # EXCLUDE lines with identical text (duplicate texts in corpus)
                        if target_text == query_text:
                            continue
                        
                        # Check for PHRASE matches (key to finding quotations!)
                        target_normalized = re.sub(r'[^\w\s]', '', target_text)
                        phrase_match_bonus = 1.0
                        
                        # Check for key phrases from query in target
                        # Phrase matches get OVERWHELMING priority to surface quotations
                        for phrase in key_phrases:
                            if phrase in target_normalized:
                                phrase_match_bonus = 1000.0 + len(phrase) * 100
                                break
                        
                        match_positions = [i for i, lem in enumerate(target_lemmas_list) if lem in shared]
                        
                        # Calculate distance (span) between matched words - V3 style
                        if len(match_positions) >= 2:
                            distance = match_positions[-1] - match_positions[0] + 1
                        else:
                            distance = 1
                        
                        # APPLY MAX_DISTANCE FILTER (same as pairwise search)
                        # Use inline prose detection (faster and more reliable than import)
                        PROSE_AUTHORS = ['cicero', 'caesar', 'livy', 'sallust', 'tacitus', 'suetonius',
                                        'nepos', 'quintilian', 'pliny', 'apuleius', 'petronius',
                                        'augustine', 'jerome', 'ambrose', 'seneca_prose',
                                        'cic.', 'caes.', 'liv.', 'sall.', 'tac.', 'suet.', 'nep.',
                                        'quint.', 'plin.', 'apul.', 'petron.', 'aug.', 'hier.', 'ambr.']
                        PROSE_MARKERS = ['epistulae', 'letters', 'de_officiis', 'de_oratore', 
                                        'de_finibus', 'de_natura', 'tusculan', 'bellum_gallicum',
                                        'historiae', 'annales', 'agricola', 'germania', 'dialogus',
                                        'satyricon', 'confessions', 'de_civitate']
                        
                        text_lower = filename.lower()
                        is_prose = any(marker in text_lower for marker in PROSE_AUTHORS + PROSE_MARKERS)
                        
                        POETRY_MAX_DISTANCE = 20
                        PROSE_MAX_DISTANCE = 4  # Very tight for compact prose phrases
                        max_dist = PROSE_MAX_DISTANCE if is_prose else POETRY_MAX_DISTANCE
                        
                        if distance > max_dist:
                            continue  # Skip results where matched words are too far apart
                        
                        # V3-STYLE SCORING: score = sum(IDF) / (1 + log(distance))
                        idf_sum = 0
                        for lemma in shared:
                            freq = corpus_frequencies.get(lemma, 1)
                            idf = math.log(total_corpus_words / (freq + 1)) + 1
                            idf_sum += idf
                        
                        # V3 distance penalty: 1 / (1 + log(distance))
                        distance_factor = 1.0 / (1 + math.log(distance + 1))
                        
                        # V3 final score: IDF sum * distance factor
                        score = idf_sum * distance_factor * phrase_match_bonus
                        
                        result_key = (filename, unit.get('ref', ''))
                        if result_key in seen_results:
                            continue
                        seen_results.add(result_key)
                        
                        tokens = unit.get('tokens', [])
                        
                        text_matches.append({
                            'text_id': filename,
                            'author': metadata.get('author', ''),
                            'work': metadata.get('title', ''),
                            'ref': unit.get('ref', ''),
                            'text': unit.get('text', ''),
                            'tokens': tokens,
                            'highlight_indices': match_positions,
                            'matched_lemmas': list(shared),
                            'match_count': len(shared),
                            'score': round(score, 3),
                            'year': author_year,
                            'era': author_era
                        })
                
                text_matches.sort(key=lambda x: x['score'], reverse=True)
                all_results.extend(text_matches[:max_per_text])
        
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Deduplicate by text content (keep highest scoring version)
        seen_texts = {}
        deduplicated = []
        for r in all_results:
            # Normalize text for comparison (lowercase, strip punctuation)
            text_key = re.sub(r'[^\w\s]', '', r['text'].lower()).strip()
            if text_key not in seen_texts:
                seen_texts[text_key] = r
                deduplicated.append(r)
            # Keep the one with the highest score (already sorted)
        
        all_results = deduplicated
        
        # Normalize scores to 0-10 range for readability
        if all_results:
            max_score = max(r['score'] for r in all_results) or 1
            for r in all_results:
                # Keep raw score for internal use, add normalized for display
                r['raw_score'] = r['score']
                r['score'] = round((r['score'] / max_score) * 10, 2)
        
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
        from backend.metrical_scanner import is_prose_text
        
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
        
        matches = find_co_occurring_lemmas(lemmas, language, min_matches=len(lemmas))
        
        results = []
        text_matches = {}
        text_genre_cache = {}
        
        POETRY_MAX_DISTANCE = 20
        PROSE_MAX_DISTANCE = 4  # Very tight for compact prose phrases
        
        # Use inline prose detection (faster and more reliable)
        PROSE_AUTHORS = ['cicero', 'caesar', 'livy', 'sallust', 'tacitus', 'suetonius',
                        'nepos', 'quintilian', 'pliny', 'apuleius', 'petronius',
                        'augustine', 'jerome', 'ambrose', 'seneca_prose',
                        'cic.', 'caes.', 'liv.', 'sall.', 'tac.', 'suet.', 'nep.',
                        'quint.', 'plin.', 'apul.', 'petron.', 'aug.', 'hier.', 'ambr.']
        PROSE_MARKERS = ['epistulae', 'letters', 'de_officiis', 'de_oratore', 
                        'de_finibus', 'de_natura', 'tusculan', 'bellum_gallicum',
                        'historiae', 'annales', 'agricola', 'germania', 'dialogus',
                        'satyricon', 'confessions', 'de_civitate']
        
        for filename, ref, matching_lemmas, positions in matches:
            if filename in exclude_texts:
                continue
            if filename not in text_genre_cache:
                text_lower = filename.lower()
                text_genre_cache[filename] = not any(marker in text_lower for marker in PROSE_AUTHORS + PROSE_MARKERS)
            
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
            filepath = os.path.join(TEXTS_DIR, language, filename)
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
        content = data.get('content', '').strip()
    
    # Only author and work are required
    if not author or not work:
        return jsonify({'error': 'Author and work title are required'}), 400
    
    try:
        with get_db_cursor() as cur:
            cur.execute('''
                INSERT INTO text_requests (name, email, author, work, language, notes, content)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (name, email, author, work, language, notes, content))
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
    data = request.get_json() or {}
    password = data.get('password', '')
    
    if not ADMIN_PASSWORD:
        return jsonify({'error': 'Admin password not configured'}), 500
    
    if password == ADMIN_PASSWORD:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Invalid password'}), 401

@api_route('/admin/requests')
def get_requests():
    """Get all text requests (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute('''
                SELECT id, name, email, author, work, language, notes, content, 
                       status, created_at, reviewed_at, reviewed_by, admin_notes
                FROM text_requests
                ORDER BY created_at DESC
            ''')
            rows = cur.fetchall()
        
        requests = []
        for row in rows:
            requests.append({
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'author': row[3],
                'work': row[4],
                'language': row[5],
                'notes': row[6],
                'content': row[7],
                'status': row[8],
                'created_at': row[9].isoformat() if row[9] else None,
                'reviewed_at': row[10].isoformat() if row[10] else None,
                'reviewed_by': row[11],
                'admin_notes': row[12]
            })
        return jsonify(requests)
    except Exception as e:
        app_logger.error(f"Failed to get text requests: {e}")
        return jsonify({'error': str(e)}), 500

@api_route('/admin/requests/<int:request_id>', methods=['PUT'])
def update_request(request_id):
    """Update a text request status (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    status = data.get('status', 'pending')
    admin_notes = data.get('admin_notes', '')
    reviewed_by = data.get('reviewed_by', 'admin')
    
    try:
        with get_db_cursor() as cur:
            cur.execute('''
                UPDATE text_requests 
                SET status = %s, admin_notes = %s, reviewed_by = %s, reviewed_at = %s
                WHERE id = %s
            ''', (status, admin_notes, reviewed_by, datetime.now(), request_id))
        return jsonify({'success': True})
    except Exception as e:
        app_logger.error(f"Failed to update text request: {e}")
        return jsonify({'error': str(e)}), 500

@api_route('/admin/requests/<int:request_id>/approve', methods=['POST'])
def approve_and_add_text(request_id):
    """Approve a request and add the text to corpus (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    final_content = data.get('content', '')
    
    try:
        with get_db_cursor() as cur:
            cur.execute('SELECT author, work, language FROM text_requests WHERE id = %s', (request_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'Request not found'}), 404
            
            author, work, language = row
            
            safe_author = ''.join(c if c.isalnum() or c in '._-' else '_' for c in author.lower())
            safe_work = ''.join(c if c.isalnum() or c in '._-' else '_' for c in work.lower())
            filename = f"{safe_author}.{safe_work}.tess"
            
            lang_dir = os.path.join(TEXTS_DIR, language)
            os.makedirs(lang_dir, exist_ok=True)
            filepath = os.path.join(lang_dir, filename)
            
            if os.path.exists(filepath):
                return jsonify({'error': f'Text "{author} - {work}" already exists in corpus'}), 409
            
            lines = final_content.strip().split('\n')
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
            
            cur.execute('''
                UPDATE text_requests 
                SET status = 'approved', reviewed_at = %s
                WHERE id = %s
            ''', (datetime.now(), request_id))
        
        recalculate_language_frequencies(language, text_processor)
        
        from backend.inverted_index import index_single_text
        index_result = index_single_text(filepath, language, text_processor)
        
        # Compute embeddings for the new text (for semantic search)
        embeddings_computed = False
        try:
            from sentence_transformers import SentenceTransformer
            from backend.precompute_embeddings import compute_embeddings_for_text
            model_name = 'all-MiniLM-L6-v2' if language == 'en' else 'bowphs/SPhilBerta'
            model = SentenceTransformer(model_name)
            success, n_lines = compute_embeddings_for_text(filepath, language, model, force=True)
            embeddings_computed = success
        except Exception as e:
            print(f"Warning: Could not compute embeddings for {filename}: {e}")
        
        return jsonify({
            'success': True,
            'filename': filename,
            'lines': len(formatted_lines),
            'indexed': index_result.get('status') == 'indexed' if index_result else False,
            'embeddings_computed': embeddings_computed
        })
    except Exception as e:
        app_logger.error(f"Failed to approve text request: {e}")
        return jsonify({'error': str(e)}), 500

@api_route('/admin/requests/<int:request_id>', methods=['DELETE'])
def delete_request(request_id):
    """Delete a text request (admin only)"""
    password = request.headers.get('X-Admin-Password', '')
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db_cursor() as cur:
            cur.execute('DELETE FROM text_requests WHERE id = %s', (request_id,))
        return jsonify({'success': True})
    except Exception as e:
        app_logger.error(f"Failed to delete text request: {e}")
        return jsonify({'error': str(e)}), 500

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
                SELECT id, name, email, feedback_type, message, status, created_at, admin_notes
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
                'status': row[5],
                'created_at': row[6].isoformat() if row[6] else None,
                'admin_notes': row[7]
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
    admin_notes = data.get('admin_notes')
    
    try:
        with get_db_cursor() as cur:
            if status and admin_notes is not None:
                cur.execute('UPDATE feedback SET status = %s, admin_notes = %s WHERE id = %s', (status, admin_notes, feedback_id))
            elif status:
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
