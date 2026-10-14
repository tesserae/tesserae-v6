"""Text requests and feedback: /request and /feedback.

Moved out of backend/app.py unchanged (application-factory job, 2026-10-12).
"""

from flask import Blueprint, jsonify, request

from backend.db_utils import get_db_cursor
from backend.email_notifications import notify_text_request, notify_feedback
from backend.runtime import (
    app_logger, api_route_for,
)

feedback_bp = Blueprint('feedback', __name__)
api_route = api_route_for(feedback_bp)

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
