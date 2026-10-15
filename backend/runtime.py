"""Shared runtime objects of the Tesserae web application.

Moved out of backend/app.py unchanged (application-factory job, 2026-10-12): the
loggers, the deployment settings, the text processor, matcher and scorer, the
processed-units cache, the author dates, the database-table setup and the
frequency-cache start-up. The blueprints import from here; backend/app.py
imports from here too and builds the Flask application around them.

What the application as a whole does (text kept from the old module docstring of
backend/app.py):
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
"""
import os
import json
import re

from backend.logging_config import setup_logging, get_logger
from backend.db_utils import get_db_cursor
from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.utils import resolve_text_path
from backend.frequency_cache import initialize_all_caches
from backend.bigram_frequency import initialize_bigram_caches
from backend.lemma_cache import get_cached_units, save_cached_units, get_file_hash

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


# Bigram tables loaded when a worker starts (opt-in).
# The first rare-pair, rare-word or search request on each web worker used to
# pay about five seconds to read a bigram table, and workers are replaced every
# 1,000 requests. TESSERAE_WARM_BIGRAMS names the languages to read in a
# background thread at start (for example "la,grc"). It is empty by default
# because each table stays in memory for the life of the worker (about 0.5 GB
# for Latin, 0.4 GB more for Greek). A request that arrives before the thread
# has finished waits for the same read (the lock in backend/bigram_frequency.py)
# and does not start a second one.
def warm_bigram_tables(languages=None):
    """Read the named bigram tables now. Returns the languages loaded."""
    from backend import bigram_frequency
    if languages is None:
        languages = [x.strip() for x in os.environ.get('TESSERAE_WARM_BIGRAMS', '').split(',')]
    loaded = []
    for lang in languages:
        if lang and bigram_frequency.is_bigram_cache_available(lang):
            try:
                if bigram_frequency.get_bigram_cache(lang):
                    loaded.append(lang)
            except Exception as e:
                app_logger.error(f"Bigram warm-up failed for {lang}: {e}")
    return loaded


def start_bigram_warmup():
    """Start the warm-up thread when TESSERAE_WARM_BIGRAMS is set."""
    if not os.environ.get('TESSERAE_WARM_BIGRAMS', '').strip():
        return None
    thread = threading.Thread(target=warm_bigram_tables, name='bigram-warmup', daemon=True)
    thread.start()
    return thread


start_bigram_warmup()


# The first Theme Search, Similar Passages or Reader gutter request on each web
# worker used to pay about 23 seconds to load the passage index (measured live
# 2026-10-15), and workers are replaced every 1,000 requests, so some visitor
# met that wait after every replacement. TESSERAE_WARM_PASSAGES=1 loads it in a
# background thread at start. Workers load it on their first such request
# anyway, so the memory is the same; only the wait moves off the visitor. The
# loader's own lock and second check mean a request that arrives during the
# warm-up waits for that load rather than starting another.
def warm_passage_index():
    """Load the passage index now. Returns True when it is loaded."""
    try:
        from backend import passage_index
        passage_index._ensure_loaded()
        return bool(passage_index._state.get('loaded'))
    except Exception as e:
        app_logger.error(f"Passage index warm-up failed: {e}")
        return False


def start_passage_warmup():
    """Start the warm-up thread when TESSERAE_WARM_PASSAGES is set."""
    if os.environ.get('TESSERAE_WARM_PASSAGES', '').strip().lower() not in ('1', 'true', 'yes'):
        return None
    thread = threading.Thread(target=warm_passage_index, name='passage-warmup', daemon=True)
    thread.start()
    return thread


start_passage_warmup()


def api_route_for(blueprint):
    """The same decorator as api_route() in backend/app.py, bound to a blueprint.

    It puts API_PREFIX in front of the path exactly as api_route() does, so a
    blueprint that uses it is registered without a url_prefix and its rules are
    the ones the application had when the routes were defined on it directly.
    """
    def api_route(path, **kwargs):
        full_path = f"{API_PREFIX}{path}" if path != "/" else API_PREFIX or "/"
        return blueprint.route(full_path, **kwargs)
    return api_route
