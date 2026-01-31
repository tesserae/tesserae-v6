"""
Tesserae V6 - Admin Blueprint
Routes for admin-only functionality
"""
from flask import Blueprint, jsonify, request
from datetime import datetime
import os
import json

from backend.db_utils import get_db_cursor
from backend.logging_config import get_logger
from backend.lemma_cache import (
    rebuild_lemma_cache, get_cache_stats as get_lemma_cache_stats,
    clear_lemma_cache
)
from backend.frequency_cache import recalculate_language_frequencies, clear_frequency_cache, get_frequency_cache_stats
from backend.cache import clear_cache as clear_search_cache, get_cache_stats as get_search_cache_stats
from backend.feature_extractor import feature_extractor
from backend.bigram_frequency import (
    calculate_bigram_frequencies, get_bigram_frequencies, 
    get_bigram_stats, is_bigram_cache_available
)

logger = get_logger('admin')

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

_admin_password = None
_author_dates = None
_author_dates_path = None
_text_processor = None
_texts_dir = None
_processed_cache = None


def init_admin_blueprint(admin_password, author_dates, author_dates_path, 
                         text_processor, texts_dir, processed_cache_ref):
    """Initialize blueprint with required dependencies"""
    global _admin_password, _author_dates, _author_dates_path
    global _text_processor, _texts_dir, _processed_cache
    _admin_password = admin_password
    _author_dates = author_dates
    _author_dates_path = author_dates_path
    _text_processor = text_processor
    _texts_dir = texts_dir
    _processed_cache = processed_cache_ref


def get_admin_username():
    """Get admin username from request header"""
    return request.headers.get('X-Admin-Username', 'unknown')


def log_admin_action(action, target_type=None, target_id=None, details=None):
    """Log an admin action to the audit log"""
    username = get_admin_username()
    try:
        with get_db_cursor() as cur:
            cur.execute('''
                INSERT INTO admin_audit_log (admin_username, action, target_type, target_id, details)
                VALUES (%s, %s, %s, %s, %s)
            ''', (username, action, target_type, target_id, json.dumps(details) if details else None))
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}")


def check_admin_auth():
    """Check admin authentication"""
    password = request.headers.get('X-Admin-Password', '')
    return password == _admin_password


@admin_bp.route('/login', methods=['POST'])
def admin_login():
    """Verify admin password"""
    data = request.get_json() or {}
    password = data.get('password', '')
    username = data.get('username', 'unknown')
    
    if not _admin_password:
        return jsonify({'error': 'Admin password not configured'}), 500
    
    if password == _admin_password:
        try:
            with get_db_cursor() as cur:
                cur.execute('''
                    INSERT INTO admin_audit_log (admin_username, action, target_type, target_id, details)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (username, 'login', None, None, None))
        except Exception as e:
            logger.error(f"Failed to log admin login: {e}")
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Invalid password'}), 401


@admin_bp.route('/requests')
def get_requests():
    """Get all text requests (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute('''
                SELECT id, name, email, author, work, language, notes, content, 
                       status, created_at, reviewed_at, reviewed_by, admin_notes,
                       text_date, approved_filename, official_author, official_work,
                       admin_updated_at
                FROM text_requests
                ORDER BY created_at DESC
            ''')
            rows = cur.fetchall()
        
        requests = []
        for row in rows:
            author = row[3]
            work = row[4]
            safe_author = ''.join(c if c.isalnum() or c in '._-' else '_' for c in (author or '').lower())
            safe_work = ''.join(c if c.isalnum() or c in '._-' else '_' for c in (work or '').lower())
            suggested_filename = f"{safe_author}.{safe_work}.tess" if author and work else ''
            
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
                'admin_notes': row[12],
                'text_date': row[13],
                'approved_filename': row[14] or suggested_filename,
                'official_author': row[15] or row[3],
                'official_work': row[16] or row[4],
                'admin_updated_at': row[17].isoformat() if row[17] else None,
                'suggested_filename': suggested_filename
            })
        return jsonify({'requests': requests})
    except Exception as e:
        logger.error(f"Failed to get text requests: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/requests/<int:request_id>', methods=['PUT'])
def update_request(request_id):
    """Update a text request (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    
    try:
        with get_db_cursor() as cur:
            cur.execute('''
                UPDATE text_requests 
                SET status = COALESCE(%s, status),
                    admin_notes = COALESCE(%s, admin_notes),
                    reviewed_by = COALESCE(%s, reviewed_by),
                    reviewed_at = %s,
                    text_date = COALESCE(%s, text_date),
                    approved_filename = COALESCE(%s, approved_filename),
                    official_author = COALESCE(%s, official_author),
                    official_work = COALESCE(%s, official_work),
                    content = COALESCE(%s, content),
                    admin_updated_at = %s
                WHERE id = %s
            ''', (
                data.get('status'),
                data.get('admin_notes'),
                data.get('reviewed_by', 'admin'),
                datetime.now(),
                data.get('text_date'),
                data.get('approved_filename'),
                data.get('official_author'),
                data.get('official_work'),
                data.get('content'),
                datetime.now(),
                request_id
            ))
        log_admin_action('update_request', 'text_request', request_id, {
            'fields_updated': list(data.keys())
        })
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Failed to update text request: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/requests/<int:request_id>/approve', methods=['POST'])
def approve_and_add_text(request_id):
    """
    Approve a request and add the text to corpus (admin only).
    
    This function performs ALL necessary updates when adding a new text:
    1. Saves .tess file to texts/{language}/
    2. Updates database request status
    3. Recalculates corpus frequencies (for stoplists)
    4. Indexes in inverted index (for lemma search)
    5. Computes semantic embeddings
    6. Updates corpus_status.json counts
    7. Adds entry to text_provenance.json
    8. Checks if author is new (needs author_dates entry)
    """
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    final_content = data.get('content', '')
    
    try:
        with get_db_cursor() as cur:
            cur.execute('''
                SELECT author, work, language, content, 
                       official_author, official_work, approved_filename
                FROM text_requests WHERE id = %s
            ''', (request_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'Request not found'}), 404
            
            orig_author, orig_work, language, db_content, official_author, official_work, approved_filename = row
            
            author = official_author or orig_author
            work = official_work or orig_work
            
            if approved_filename and approved_filename.endswith('.tess'):
                filename = approved_filename
                text_id = approved_filename[:-5]
            else:
                safe_author = ''.join(c if c.isalnum() or c in '._-' else '_' for c in author.lower())
                safe_work = ''.join(c if c.isalnum() or c in '._-' else '_' for c in work.lower())
                filename = f"{safe_author}.{safe_work}.tess"
                text_id = f"{safe_author}.{safe_work}"
            
            safe_author = ''.join(c if c.isalnum() or c in '._-' else '_' for c in author.lower())
            safe_work = ''.join(c if c.isalnum() or c in '._-' else '_' for c in work.lower())
            
            lang_dir = os.path.join(_texts_dir, language)
            os.makedirs(lang_dir, exist_ok=True)
            filepath = os.path.join(lang_dir, filename)
            
            if os.path.exists(filepath):
                return jsonify({'error': f'Text "{author} - {work}" already exists in corpus'}), 409
            
            content_to_use = final_content if final_content else db_content
            if not content_to_use:
                return jsonify({'error': 'No text content provided'}), 400
            
            lines = content_to_use.strip().split('\n')
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
        
        # Step 3: Recalculate corpus frequencies (including bigram index)
        recalculate_language_frequencies(language, _text_processor)
        
        # Also update bigram frequencies if cache exists
        from backend.bigram_frequency import is_bigram_cache_available, calculate_bigram_frequencies
        if is_bigram_cache_available(language):
            calculate_bigram_frequencies(language, _text_processor)
        
        # Step 3b: Regenerate rare words cache (depends on fresh frequency data)
        from backend.blueprints.hapax import regenerate_rare_words_cache
        try:
            regenerate_rare_words_cache(language)
        except Exception as e:
            logger.warning(f"Could not regenerate rare words cache: {e}")
        
        # Step 4: Index in inverted index
        from backend.inverted_index import index_single_text
        index_result = index_single_text(filepath, language, _text_processor)
        
        # Step 5: Compute embeddings for the new text (for semantic search)
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
        
        # Step 6: Clear search results cache for this language
        from backend.cache import clear_cache_for_language
        cache_cleared = clear_cache_for_language(language)
        
        # Step 7: Update corpus_status.json counts
        _update_corpus_status(language)
        
        # Step 7: Add to text_provenance.json
        _update_text_provenance(text_id, author, work, language)
        
        # Step 8: Check if author is new (not in author_dates)
        author_key = safe_author.replace('.', '_').replace('-', '_')
        is_new_author = not (_author_dates and 
                            language in _author_dates and 
                            author_key in _author_dates[language])
        
        log_admin_action('approve_request', 'text_request', request_id, {
            'filename': filename,
            'author': author,
            'work': work,
            'language': language,
            'lines': len(formatted_lines)
        })
        
        return jsonify({
            'success': True,
            'filename': filename,
            'lines': len(formatted_lines),
            'indexed': index_result.get('status') == 'indexed' if index_result else False,
            'embeddings_computed': embeddings_computed,
            'is_new_author': is_new_author,
            'author_key': author_key if is_new_author else None,
            'message': f"Text added successfully. {'Note: Author dates not set - please add via Admin > Author Dates.' if is_new_author else ''}"
        })
    except Exception as e:
        logger.error(f"Failed to approve text request: {e}")
        return jsonify({'error': str(e)}), 500


def _update_corpus_status(language):
    """Update corpus_status.json with new text count for the given language."""
    try:
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        status_path = os.path.join(backend_dir, 'corpus_status.json')
        
        if not os.path.exists(status_path):
            logger.warning("corpus_status.json not found, skipping update")
            return
        
        with open(status_path, 'r') as f:
            status = json.load(f)
        
        # Count actual .tess files
        tess_count = 0
        if _texts_dir:
            lang_dir = os.path.join(_texts_dir, language)
            if os.path.exists(lang_dir):
                tess_count = len([f for f in os.listdir(lang_dir) if f.endswith('.tess')])
        
        if 'summary' not in status:
            status['summary'] = {}
        if 'total_texts' not in status['summary']:
            status['summary']['total_texts'] = {}
        status['summary']['total_texts'][language] = tess_count
        status['_last_updated'] = datetime.now().strftime('%Y-%m-%d')
        
        with open(status_path, 'w') as f:
            json.dump(status, f, indent=2)
        
        logger.info(f"Updated corpus_status.json: {language} = {tess_count} texts")
    except Exception as e:
        logger.error(f"Failed to update corpus_status.json: {e}")


def _update_text_provenance(text_id, author, title, language):
    """Add a new text entry to text_provenance.json."""
    try:
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        prov_path = os.path.join(backend_dir, 'text_provenance.json')
        
        if not os.path.exists(prov_path):
            logger.warning("text_provenance.json not found, skipping update")
            return
        
        with open(prov_path, 'r') as f:
            provenance = json.load(f)
        
        # Ensure required dicts exist
        if 'texts' not in provenance:
            provenance['texts'] = {}
        if 'sources' not in provenance:
            provenance['sources'] = {}
        
        # Add user_submission source if not present
        if 'user_submission' not in provenance['sources']:
            provenance['sources']['user_submission'] = {
                "name": "User Submission",
                "url": "",
                "description": "Texts submitted by users and approved by administrators"
            }
        
        provenance['texts'][text_id] = {
            "source": "user_submission",
            "original_id": None,
            "author": author,
            "title": title,
            "date_added": datetime.now().isoformat(),
            "language": language
        }
        
        with open(prov_path, 'w') as f:
            json.dump(provenance, f, indent=2)
        
        logger.info(f"Added {text_id} to text_provenance.json")
    except Exception as e:
        logger.error(f"Failed to update text_provenance.json: {e}")


@admin_bp.route('/requests/<int:request_id>', methods=['DELETE'])
def delete_request(request_id):
    """Delete a text request (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute('SELECT author, work FROM text_requests WHERE id = %s', (request_id,))
            row = cur.fetchone()
        with get_db_cursor() as cur:
            cur.execute('DELETE FROM text_requests WHERE id = %s', (request_id,))
        log_admin_action('delete_request', 'text_request', request_id, {
            'author': row[0] if row else None,
            'work': row[1] if row else None
        })
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Failed to delete text request: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/author-dates', methods=['GET'])
def get_author_dates():
    """Get all author dates (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify(_author_dates)


@admin_bp.route('/author-dates/<language>/<author_key>', methods=['PUT'])
def update_author_date(language, author_key):
    """Update or add an author date entry (admin only)"""
    global _author_dates
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    year = data.get('year')
    era = data.get('era', 'Unknown')
    note = data.get('note', '')
    
    if language not in _author_dates:
        _author_dates[language] = {}
    
    _author_dates[language][author_key] = {
        'year': int(year) if year is not None and year != '' else None,
        'era': era,
        'note': note
    }
    
    with open(_author_dates_path, 'w') as f:
        json.dump(_author_dates, f, indent=2)
    
    return jsonify({'success': True})


@admin_bp.route('/author-dates/<language>/<author_key>', methods=['DELETE'])
def delete_author_date(language, author_key):
    """Delete an author date entry (admin only)"""
    global _author_dates
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    if language in _author_dates and author_key in _author_dates[language]:
        del _author_dates[language][author_key]
        with open(_author_dates_path, 'w') as f:
            json.dump(_author_dates, f, indent=2)
        return jsonify({'success': True})
    
    return jsonify({'error': 'Entry not found'}), 404


@admin_bp.route('/lemma-cache/stats', methods=['GET'])
def lemma_cache_stats():
    """Get lemma cache statistics (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify(get_lemma_cache_stats())


@admin_bp.route('/lemma-cache/rebuild', methods=['POST'])
def rebuild_lemma_cache_endpoint():
    """Rebuild lemma cache for a language (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    language = data.get('language', 'la')
    
    if _processed_cache is not None:
        _processed_cache.clear()
    
    result = rebuild_lemma_cache(language, _text_processor)
    return jsonify(result)


@admin_bp.route('/lemma-cache/clear', methods=['POST'])
def clear_lemma_cache_endpoint():
    """Clear lemma cache (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    language = data.get('language')
    
    if _processed_cache is not None:
        _processed_cache.clear()
    
    result = clear_lemma_cache(language)
    return jsonify(result)


@admin_bp.route('/search-cache/clear', methods=['POST'])
def clear_search_cache_endpoint():
    """Clear search results cache (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    count = clear_search_cache()
    return jsonify({'success': True, 'cleared': count})


@admin_bp.route('/search-cache/stats', methods=['GET'])
def search_cache_stats():
    """Get search cache statistics (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    return jsonify(get_search_cache_stats())


@admin_bp.route('/frequency-cache/clear', methods=['POST'])
def clear_frequency_cache_endpoint():
    """Clear frequency cache (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    language = data.get('language')
    
    result = clear_frequency_cache(language)
    return jsonify({'success': True, **result})


@admin_bp.route('/frequency-cache/stats', methods=['GET'])
def frequency_cache_stats():
    """Get frequency cache statistics (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    return jsonify(get_frequency_cache_stats())


@admin_bp.route('/bigram-cache/stats', methods=['GET'])
def bigram_cache_stats():
    """Get bigram cache statistics (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    stats = {}
    for lang in ['la', 'grc', 'en']:
        if is_bigram_cache_available(lang):
            stats[lang] = get_bigram_stats(lang)
        else:
            stats[lang] = None
    return jsonify(stats)


@admin_bp.route('/bigram-cache/build', methods=['POST'])
def build_bigram_cache():
    """Build bigram frequency cache for a language (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    language = data.get('language', 'la')
    
    if language not in ['la', 'grc', 'en']:
        return jsonify({'error': 'Invalid language'}), 400
    
    try:
        result = calculate_bigram_frequencies(language, _text_processor)
        if result:
            return jsonify({
                'success': True,
                'language': language,
                'unique_bigrams': len(result.get('frequencies', {})),
                'total_occurrences': result.get('total_bigrams', 0),
                'total_docs': result.get('total_docs', 0)
            })
        else:
            return jsonify({'error': 'Failed to build bigram cache'}), 500
    except Exception as e:
        logger.error(f"Failed to build bigram cache for {language}: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/feedback', methods=['GET'])
def get_feedback():
    """Get all feedback submissions (admin only)"""
    if not check_admin_auth():
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
        logger.error(f"Failed to get feedback: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/feedback/<int:feedback_id>', methods=['PUT'])
def update_feedback(feedback_id):
    """Update feedback status (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    status = data.get('status')
    admin_notes = data.get('admin_notes')
    
    try:
        with get_db_cursor() as cur:
            if status and admin_notes is not None:
                cur.execute('UPDATE feedback SET status = %s, admin_notes = %s WHERE id = %s', 
                           (status, admin_notes, feedback_id))
            elif status:
                cur.execute('UPDATE feedback SET status = %s WHERE id = %s', (status, feedback_id))
            elif admin_notes is not None:
                cur.execute('UPDATE feedback SET admin_notes = %s WHERE id = %s', (admin_notes, feedback_id))
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Failed to update feedback: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/settings', methods=['GET'])
def get_settings():
    """Get admin settings (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute('SELECT key, value FROM settings')
            rows = cur.fetchall()
        
        settings = {row[0]: row[1] for row in rows}
        return jsonify(settings)
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/settings', methods=['POST'])
def update_settings():
    """Update admin settings (admin only)"""
    if not check_admin_auth():
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
        logger.error(f"Failed to update settings: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/user-data', methods=['GET'])
def get_user_data():
    """Get all data for a user by email (GDPR data export)"""
    if not check_admin_auth():
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
            
            cur.execute('SELECT id, author, work, language, status, created_at FROM text_requests WHERE email ILIKE %s', (email,))
            request_rows = cur.fetchall()
            result['text_requests'] = [{
                'id': row[0],
                'author': row[1],
                'work': row[2],
                'language': row[3],
                'status': row[4],
                'created_at': str(row[5]) if row[5] else None
            } for row in request_rows]
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Failed to get user data: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/analytics', methods=['GET'])
def get_analytics():
    """Get search analytics (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute('SELECT COUNT(*) FROM search_logs')
            total_row = cur.fetchone()
            total_searches = total_row[0] if total_row else 0
            
            cur.execute('''
                SELECT COUNT(*) FROM search_logs 
                WHERE DATE(created_at) = CURRENT_DATE
            ''')
            today_row = cur.fetchone()
            searches_today = today_row[0] if today_row else 0
            
            cur.execute('''
                SELECT COUNT(DISTINCT user_id) FROM search_logs 
                WHERE user_id IS NOT NULL
            ''')
            users_row = cur.fetchone()
            unique_users = users_row[0] if users_row else 0
            
            cur.execute('''
                SELECT search_type, COUNT(*) 
                FROM search_logs 
                GROUP BY search_type
                ORDER BY COUNT(*) DESC
            ''')
            type_rows = cur.fetchall()
            by_type = [{'type': row[0] or 'unknown', 'count': row[1]} for row in type_rows]
            
            cur.execute('''
                SELECT language, COUNT(*) 
                FROM search_logs 
                GROUP BY language
                ORDER BY COUNT(*) DESC
            ''')
            lang_rows = cur.fetchall()
            by_language = [{'language': row[0] or 'unknown', 'count': row[1]} for row in lang_rows]
            
            cur.execute('''
                SELECT DATE(created_at) as day, COUNT(*) 
                FROM search_logs 
                WHERE created_at > NOW() - INTERVAL '30 days'
                GROUP BY DATE(created_at)
                ORDER BY day DESC
            ''')
            daily_rows = cur.fetchall()
            per_day = [{'date': str(row[0]), 'count': row[1]} for row in daily_rows]
            
            cur.execute('''
                SELECT source_text, COUNT(*) 
                FROM search_logs 
                WHERE source_text IS NOT NULL
                GROUP BY source_text
                ORDER BY COUNT(*) DESC
                LIMIT 10
            ''')
            source_rows = cur.fetchall()
            top_sources = [{'text': row[0], 'count': row[1]} for row in source_rows]
            
            cur.execute('''
                SELECT target_text, COUNT(*) 
                FROM search_logs 
                WHERE target_text IS NOT NULL
                GROUP BY target_text
                ORDER BY COUNT(*) DESC
                LIMIT 10
            ''')
            target_rows = cur.fetchall()
            top_targets = [{'text': row[0], 'count': row[1]} for row in target_rows]
            
            cur.execute('''
                SELECT country, COUNT(*) 
                FROM search_logs 
                WHERE country IS NOT NULL
                GROUP BY country
                ORDER BY COUNT(*) DESC
                LIMIT 10
            ''')
            country_rows = cur.fetchall()
            top_countries = [{'country': row[0], 'count': row[1]} for row in country_rows]
            
            cur.execute('''
                SELECT city, country, COUNT(*) 
                FROM search_logs 
                WHERE city IS NOT NULL
                GROUP BY city, country
                ORDER BY COUNT(*) DESC
                LIMIT 10
            ''')
            city_rows = cur.fetchall()
            top_cities = [{'city': row[0], 'country': row[1] or '', 'count': row[2]} for row in city_rows]
            
            cur.execute('''
                SELECT query_text, language 
                FROM search_logs 
                WHERE query_text IS NOT NULL AND query_text != ''
                ORDER BY created_at DESC
                LIMIT 20
            ''')
            query_rows = cur.fetchall()
            recent_queries = [{'query': row[0], 'language': row[1] or 'unknown'} for row in query_rows]
        
        return jsonify({
            'total_searches': total_searches,
            'searches_today': searches_today,
            'unique_users': unique_users,
            'cache_hits': 0,
            'cache_misses': 0,
            'by_type': by_type,
            'by_language': by_language,
            'per_day': per_day,
            'top_sources': top_sources,
            'top_targets': top_targets,
            'top_countries': top_countries,
            'top_cities': top_cities,
            'recent_queries': recent_queries
        })
    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/features/weights', methods=['GET'])
def get_feature_weights():
    """Get current feature weights"""
    return jsonify(feature_extractor.get_weights())


@admin_bp.route('/features/weights', methods=['POST'])
def update_feature_weights():
    """Update feature weights (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    success = feature_extractor.set_weights(data)
    
    if success:
        return jsonify({'success': True, 'weights': feature_extractor.get_weights()})
    else:
        return jsonify({'error': 'Failed to save weights'}), 500


@admin_bp.route('/features/toggle', methods=['POST'])
def toggle_feature():
    """Toggle a feature on/off (admin only)"""
    if not check_admin_auth():
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


@admin_bp.route('/embeddings/status')
def get_embedding_status():
    """Get status of pre-computed embeddings (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        from backend.embedding_storage import get_embedding_stats, load_manifest
        stats = get_embedding_stats()
        manifest = load_manifest()
        
        computed_texts = list(manifest.get('texts', {}).keys())
        
        return jsonify({
            'stats': stats,
            'computed_count': len(computed_texts),
            'computed_texts': computed_texts[:50]
        })
    except Exception as e:
        logger.error(f"Failed to get embedding status: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/embeddings/compute', methods=['POST'])
def compute_embeddings():
    """Trigger embedding pre-computation (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    language = data.get('language')
    force = data.get('force', False)
    text_path = data.get('text_path')
    
    try:
        if text_path:
            from backend.precompute_embeddings import compute_embeddings_for_text, parse_tess_file
            from sentence_transformers import SentenceTransformer
            from backend.embedding_storage import has_embeddings
            
            if not force and has_embeddings(text_path, language or 'la'):
                return jsonify({
                    'success': True,
                    'message': 'Embeddings already exist',
                    'skipped': True
                })
            
            model_name = 'all-MiniLM-L6-v2' if language == 'en' else 'bowphs/SPhilBerta'
            model = SentenceTransformer(model_name)
            
            success, n_lines = compute_embeddings_for_text(
                text_path, language or 'la', model, force
            )
            
            return jsonify({
                'success': success,
                'lines_processed': n_lines,
                'text': text_path
            })
        else:
            from backend.precompute_embeddings import precompute_all
            
            stats = precompute_all(language=language, force=force)
            
            return jsonify({
                'success': True,
                'processed': stats['processed'],
                'skipped': stats['skipped'],
                'failed': stats['failed'],
                'total_lines': stats['total_lines'],
                'elapsed_time': stats['elapsed_time']
            })
            
    except Exception as e:
        logger.error(f"Failed to compute embeddings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/embeddings/clear', methods=['POST'])
def clear_embeddings():
    """Clear all pre-computed embeddings (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        from backend.embedding_storage import clear_all_embeddings
        success = clear_all_embeddings()
        
        if success:
            return jsonify({'success': True, 'message': 'All embeddings cleared'})
        else:
            return jsonify({'error': 'Failed to clear embeddings'}), 500
    except Exception as e:
        logger.error(f"Failed to clear embeddings: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/audit-log', methods=['GET'])
def get_audit_log():
    """Get admin audit log entries (admin only)"""
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        limit = request.args.get('limit', 100, type=int)
        
        with get_db_cursor() as cur:
            cur.execute('''
                SELECT id, admin_username, action, target_type, target_id, details, created_at
                FROM admin_audit_log
                ORDER BY created_at DESC
                LIMIT %s
            ''', (limit,))
            rows = cur.fetchall()
            
            entries = []
            for row in rows:
                entries.append({
                    'id': row[0],
                    'admin_username': row[1],
                    'action': row[2],
                    'target_type': row[3],
                    'target_id': row[4],
                    'details': row[5],
                    'created_at': row[6].isoformat() if row[6] else None
                })
            
            return jsonify({'entries': entries})
    except Exception as e:
        logger.error(f"Failed to fetch audit log: {e}")
        return jsonify({'error': str(e)}), 500
