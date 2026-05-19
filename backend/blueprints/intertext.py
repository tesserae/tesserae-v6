"""
Intertext Repository Blueprint
Handles saving, browsing, and exporting registered intertexts.
"""
from flask import Blueprint, jsonify, request, session
from flask_login import current_user
from datetime import datetime
import json
import csv
import io

from backend.models import db, Intertext, SavedIntertext, User
from backend.logging_config import get_logger

logger = get_logger(__name__)

intertext_bp = Blueprint('intertext', __name__, url_prefix='/intertexts')


def _parse_json_list(raw_value):
    if not raw_value:
        return []
    try:
        return json.loads(raw_value)
    except (TypeError, ValueError):
        return []


def _serialize_public_intertext(it):
    # Resolve submitter display info: prefer cached columns, fall back to User relationship
    user_obj = getattr(it, 'submitter', None)
    cached_name = (it.submitter_name or '').strip()
    cached_email = (it.submitter_email or '').strip()

    if not cached_name and user_obj:
        cached_name = f"{user_obj.first_name or ''} {user_obj.last_name or ''}".strip() or (user_obj.email or '')
    if not cached_email and user_obj:
        cached_email = user_obj.email or ''

    # Build a username display: try full name, fall back to email prefix, then "Anonymous"
    username_display = cached_name or (cached_email.split('@')[0] if cached_email else 'Anonymous')

    return {
        'id': it.id,
        'source': {
            'text_id': it.source_text_id,
            'author': it.source_author,
            'work': it.source_work,
            'reference': it.source_reference,
            'snippet': it.source_snippet,
            'language': it.source_language
        },
        'target': {
            'text_id': it.target_text_id,
            'author': it.target_author,
            'work': it.target_work,
            'reference': it.target_reference,
            'snippet': it.target_snippet,
            'language': it.target_language
        },
        'matched_lemmas': _parse_json_list(it.matched_lemmas),
        'matched_tokens': _parse_json_list(it.matched_tokens),
        'tesserae_score': it.tesserae_score,
        'user_score': it.user_score,
        'submitter_id': it.submitter_id,
        'submitter': {
            'name': cached_name,
            'username': username_display,
            'email': cached_email,
            'institution': it.submitter_institution or '',
            'orcid': it.submitter_orcid or ''
        },
        'notes': it.notes,
        'tags': _parse_json_list(it.tags),
        'status': it.status,
        'created_at': it.created_at.isoformat() if it.created_at else None
    }



def _serialize_saved_intertext(it):
    return {
        'id': it.id,
        'source': {
            'text_id': it.source_text_id,
            'author': it.source_author,
            'work': it.source_work,
            'reference': it.source_reference,
            'snippet': it.source_snippet,
            'language': it.source_language
        },
        'target': {
            'text_id': it.target_text_id,
            'author': it.target_author,
            'work': it.target_work,
            'reference': it.target_reference,
            'snippet': it.target_snippet,
            'language': it.target_language
        },
        'matched_lemmas': _parse_json_list(it.matched_lemmas),
        'matched_tokens': _parse_json_list(it.matched_tokens),
        'tesserae_score': it.tesserae_score,
        'intertext_score': it.intertext_score,
        'notes': it.notes,
        'tags': _parse_json_list(it.tags),
        'shared_to_public': it.shared_to_public,
        'public_intertext_id': it.public_intertext_id,
        'created_at': it.created_at.isoformat() if it.created_at else None
    }


def _build_public_intertext(source, target, data, submitter):
    user_name = f"{submitter.first_name or ''} {submitter.last_name or ''}".strip() or submitter.email
    return Intertext(
        source_text_id=source.get('text_id', ''),
        source_author=source.get('author', ''),
        source_work=source.get('work', ''),
        source_reference=source.get('reference', ''),
        source_snippet=source.get('snippet', ''),
        source_language=source.get('language', 'la'),
        target_text_id=target.get('text_id', ''),
        target_author=target.get('author', ''),
        target_work=target.get('work', ''),
        target_reference=target.get('reference', ''),
        target_snippet=target.get('snippet', ''),
        target_language=target.get('language', 'la'),
        matched_lemmas=json.dumps(data.get('matched_lemmas', [])),
        matched_tokens=json.dumps(data.get('matched_tokens', [])),
        tesserae_score=data.get('tesserae_score', 0.0),
        user_score=data.get('intertext_score', data.get('user_score', 0)),
        submitter_id=submitter.id,
        submitter_name=user_name,
        submitter_email=submitter.email or '',
        submitter_institution=submitter.institution or '',
        submitter_orcid=submitter.orcid or '',
        notes=data.get('notes', ''),
        tags=json.dumps(data.get('tags', [])),
        status='pending',
        created_at=datetime.now()
    )


def _sync_public_intertext(public_it, saved_it, submitter):
    """Keep an existing public intertext aligned with the saved copy."""
    user_name = f"{submitter.first_name or ''} {submitter.last_name or ''}".strip() or submitter.email
    public_it.source_text_id = saved_it.source_text_id
    public_it.source_author = saved_it.source_author
    public_it.source_work = saved_it.source_work
    public_it.source_reference = saved_it.source_reference
    public_it.source_snippet = saved_it.source_snippet
    public_it.source_language = saved_it.source_language
    public_it.target_text_id = saved_it.target_text_id
    public_it.target_author = saved_it.target_author
    public_it.target_work = saved_it.target_work
    public_it.target_reference = saved_it.target_reference
    public_it.target_snippet = saved_it.target_snippet
    public_it.target_language = saved_it.target_language
    public_it.matched_lemmas = saved_it.matched_lemmas
    public_it.matched_tokens = saved_it.matched_tokens
    public_it.tesserae_score = saved_it.tesserae_score
    public_it.user_score = saved_it.intertext_score
    public_it.submitter_id = submitter.id
    public_it.submitter_name = user_name
    public_it.submitter_email = submitter.email or ''
    public_it.submitter_institution = submitter.institution or ''
    public_it.submitter_orcid = submitter.orcid or ''
    public_it.notes = saved_it.notes
    public_it.tags = saved_it.tags


def _delete_public_copy(saved_it):
    if not saved_it.public_intertext_id:
        return
    public_it = Intertext.query.get(saved_it.public_intertext_id)
    if public_it:
        db.session.delete(public_it)
    saved_it.public_intertext_id = None


@intertext_bp.route('', methods=['GET'])
def list_intertexts():
    """List all intertexts with optional filtering"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        status = request.args.get('status', None)
        source_language = request.args.get('source_language', None)
        target_language = request.args.get('target_language', None)
        tag = request.args.get('tag', None)
        submitter_id = request.args.get('submitter_id', None)
        
        query = Intertext.query
        
        if status:
            query = query.filter(Intertext.status == status)
        if source_language:
            query = query.filter(Intertext.source_language == source_language)
        if target_language:
            query = query.filter(Intertext.target_language == target_language)
        if tag:
            query = query.filter(Intertext.tags.ilike(f'%{tag}%'))
        if submitter_id:
            query = query.filter(Intertext.submitter_id == submitter_id)
        
        query = query.order_by(Intertext.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        intertexts = [_serialize_public_intertext(it) for it in pagination.items]
        
        return jsonify({
            'intertexts': intertexts,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page
        })
    except Exception as e:
        logger.error(f"Failed to list intertexts: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('', methods=['POST'])
def register_intertext():
    """Register a new intertext from search results"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        source = data.get('source', {})
        target = data.get('target', {})
        
        if not source.get('text_id') or not target.get('text_id'):
            return jsonify({'error': 'Source and target text_id required'}), 400
        
        submitter_info = data.get('submitter', {})
        intertext = Intertext(
            source_text_id=source.get('text_id', ''),
            source_author=source.get('author', ''),
            source_work=source.get('work', ''),
            source_reference=source.get('reference', ''),
            source_snippet=source.get('snippet', ''),
            source_language=source.get('language', 'la'),
            target_text_id=target.get('text_id', ''),
            target_author=target.get('author', ''),
            target_work=target.get('work', ''),
            target_reference=target.get('reference', ''),
            target_snippet=target.get('snippet', ''),
            target_language=target.get('language', 'la'),
            matched_lemmas=json.dumps(data.get('matched_lemmas', [])),
            matched_tokens=json.dumps(data.get('matched_tokens', [])),
            tesserae_score=data.get('tesserae_score', 0.0),
            user_score=data.get('user_score', 0),
            submitter_id=current_user.id if current_user and current_user.is_authenticated else None,
            submitter_name=submitter_info.get('name', ''),
            submitter_email=submitter_info.get('email', ''),
            submitter_institution=submitter_info.get('institution', ''),
            submitter_orcid=submitter_info.get('orcid', '') or (current_user.orcid if current_user and current_user.is_authenticated else None),
            notes=data.get('notes', ''),
            tags=json.dumps(data.get('tags', [])),
            status='pending',
            created_at=datetime.now()
        )
        
        db.session.add(intertext)
        db.session.commit()
        
        logger.info(f"Registered intertext {intertext.id}: {source.get('reference')} -> {target.get('reference')}")
        
        return jsonify({
            'success': True,
            'id': intertext.id,
            'message': 'Intertext registered successfully'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to register intertext: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/<int:intertext_id>', methods=['GET'])
def get_intertext(intertext_id):
    """Get a single intertext by ID"""
    try:
        it = Intertext.query.get(intertext_id)
        if not it:
            return jsonify({'error': 'Intertext not found'}), 404
        
        return jsonify(_serialize_public_intertext(it))
    except Exception as e:
        logger.error(f"Failed to get intertext: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/<int:intertext_id>', methods=['PUT'])
def update_intertext(intertext_id):
    """Update an intertext (notes, tags, user_score) - requires authentication"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Login required to update intertexts'}), 401
        
        it = Intertext.query.get(intertext_id)
        if not it:
            return jsonify({'error': 'Intertext not found'}), 404
        
        is_owner = it.submitter_id == current_user.id
        if not is_owner:
            return jsonify({'error': 'Only the submitter can edit this intertext'}), 403
        
        data = request.get_json()
        
        if 'notes' in data:
            it.notes = data['notes']
        if 'tags' in data:
            it.tags = json.dumps(data['tags'])
        if 'user_score' in data:
            it.user_score = data['user_score']
        if 'status' in data:
            it.status = data['status']
            if data['status'] in ('confirmed', 'rejected'):
                it.reviewed_at = datetime.now()
                it.reviewed_by = current_user.id
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to update intertext: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/<int:intertext_id>', methods=['PATCH'])
def flag_intertext(intertext_id):
    """Flag/unflag an intertext - requires authentication.
    Flagging: any logged-in user.
    Unflagging (confirmed/pending): admins only."""
    try:
        # Require authentication for all flag operations
        user_id = current_user.id if current_user.is_authenticated else session.get('admin_user_id')
        if not user_id:
            return jsonify({'error': 'Login required to flag intertexts'}), 401

        it = Intertext.query.get(intertext_id)
        if not it:
            return jsonify({'error': 'Intertext not found'}), 404

        data = request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify({'error': 'Invalid request body'}), 400

        new_status = data.get('status')
        if new_status == 'flagged':
            # Any authenticated user can flag
            it.status = 'flagged'
            db.session.commit()
            return jsonify({'success': True})
        elif new_status in ('confirmed', 'pending'):
            # Only admins can unflag
            admin_roles = session.get('admin_roles', [])
            is_admin = ('ADMIN' in admin_roles or 'SUPER_ADMIN' in admin_roles)
            if not is_admin and current_user.is_authenticated:
                from sqlalchemy import text as sql_text
                result = db.session.execute(
                    sql_text("SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id = r.id WHERE ur.user_id = :uid"),
                    {'uid': current_user.id}
                )
                roles = [row[0] for row in result.fetchall()]
                is_admin = 'ADMIN' in roles or 'SUPER_ADMIN' in roles
            if not is_admin:
                return jsonify({'error': 'Only admins can unflag intertexts'}), 403
            it.status = new_status
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Invalid status - must be flagged, confirmed, or pending'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to flag intertext: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/<int:intertext_id>', methods=['DELETE'])
def delete_intertext(intertext_id):
    """Delete an intertext - requires authentication and ownership"""
    try:
        user_id = current_user.id if current_user.is_authenticated else session.get('admin_user_id')
        if not user_id:
            return jsonify({'error': 'Login required to delete intertexts'}), 401
        
        it = Intertext.query.get(intertext_id)
        if not it:
            return jsonify({'error': 'Intertext not found'}), 404
        
        admin_roles = session.get('admin_roles', [])
        is_admin = ('ADMIN' in admin_roles or 'SUPER_ADMIN' in admin_roles)
        if not is_admin and current_user.is_authenticated:
            from sqlalchemy import text
            result = db.session.execute(
                text("SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id = r.id WHERE ur.user_id = :uid"),
                {'uid': current_user.id}
            )
            roles = [row[0] for row in result.fetchall()]
            is_admin = 'ADMIN' in roles or 'SUPER_ADMIN' in roles
        
        if str(it.submitter_id) != str(user_id) and not is_admin:
            return jsonify({'error': 'Only the submitter or an admin can delete this intertext'}), 403

        for saved_copy in list(it.saved_copies):
            saved_copy.shared_to_public = False
            saved_copy.public_intertext_id = None

        db.session.delete(it)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to delete intertext: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/export', methods=['GET'])
def export_intertexts():
    """Export intertexts to CSV or JSON"""
    try:
        format_type = request.args.get('format', 'json')
        status = request.args.get('status', None)
        
        query = Intertext.query
        if status:
            query = query.filter(Intertext.status == status)
        
        intertexts = query.order_by(Intertext.created_at.desc()).all()
        
        if format_type == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'id', 'source_text_id', 'source_author', 'source_work', 'source_reference', 'source_snippet', 'source_language',
                'target_text_id', 'target_author', 'target_work', 'target_reference', 'target_snippet', 'target_language',
                'matched_lemmas', 'matched_tokens', 'tesserae_score', 'user_score',
                'notes', 'tags', 'status', 'created_at'
            ])
            
            for it in intertexts:
                writer.writerow([
                    it.id, it.source_text_id, it.source_author, it.source_work, it.source_reference, it.source_snippet, it.source_language,
                    it.target_text_id, it.target_author, it.target_work, it.target_reference, it.target_snippet, it.target_language,
                    it.matched_lemmas, it.matched_tokens, it.tesserae_score, it.user_score,
                    it.notes, it.tags, it.status, 
                    it.created_at.isoformat() if it.created_at else ''
                ])
            
            from flask import Response
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=intertexts.csv'}
            )
        else:
            data = []
            for it in intertexts:
                data.append({
                    'id': it.id,
                    'source': {
                        'text_id': it.source_text_id,
                        'author': it.source_author,
                        'work': it.source_work,
                        'reference': it.source_reference,
                        'snippet': it.source_snippet,
                        'language': it.source_language
                    },
                    'target': {
                        'text_id': it.target_text_id,
                        'author': it.target_author,
                        'work': it.target_work,
                        'reference': it.target_reference,
                        'snippet': it.target_snippet,
                        'language': it.target_language
                    },
                    'matched_lemmas': json.loads(it.matched_lemmas) if it.matched_lemmas else [],
                    'matched_tokens': json.loads(it.matched_tokens) if it.matched_tokens else [],
                    'tesserae_score': it.tesserae_score,
                    'user_score': it.user_score,
                    'notes': it.notes,
                    'tags': json.loads(it.tags) if it.tags else [],
                    'status': it.status,
                    'created_at': it.created_at.isoformat() if it.created_at else None
                })
            
            from flask import Response
            return Response(
                json.dumps(data, indent=2),
                mimetype='application/json',
                headers={'Content-Disposition': 'attachment; filename=intertexts.json'}
            )
    except Exception as e:
        logger.error(f"Failed to export intertexts: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get intertext repository statistics"""
    try:
        total = Intertext.query.count()
        flagged = Intertext.query.filter(Intertext.status == 'flagged').count()
        
        by_source_lang = db.session.query(
            Intertext.source_language, 
            db.func.count(Intertext.id)
        ).group_by(Intertext.source_language).all()
        
        return jsonify({
            'total': total,
            'flagged': flagged,
            'by_source_language': {lang: count for lang, count in by_source_lang}
        })
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/my', methods=['GET'])
def list_my_intertexts():
    """List user's personal saved intertexts"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Login required'}), 401
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        query = SavedIntertext.query.filter(SavedIntertext.user_id == current_user.id)
        query = query.order_by(SavedIntertext.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        intertexts = [_serialize_saved_intertext(it) for it in pagination.items]
        
        return jsonify({
            'intertexts': intertexts,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        })
    except Exception as e:
        logger.error(f"Failed to list personal intertexts: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/my/<int:saved_id>', methods=['PATCH'])
def update_saved_intertext(saved_id):
    """Update a saved intertext in the user's personal collection."""
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Login required'}), 401

        saved_it = SavedIntertext.query.get(saved_id)
        if not saved_it:
            return jsonify({'error': 'Saved intertext not found'}), 404
        if saved_it.user_id != current_user.id:
            return jsonify({'error': 'Not authorized'}), 403

        data = request.get_json() or {}

        if 'notes' in data:
            saved_it.notes = (data.get('notes') or '').strip()[:500]
        if 'tags' in data:
            saved_it.tags = json.dumps(data.get('tags') or [])
        if 'intertext_score' in data:
            score = data.get('intertext_score')
            if not isinstance(score, int) or score < 1 or score > 5:
                return jsonify({'error': 'Valid intertext_score (1-5) required'}), 400
            saved_it.intertext_score = score
        if 'shared_to_public' in data:
            should_share = bool(data.get('shared_to_public'))
            if should_share and not saved_it.shared_to_public:
                public_it = _build_public_intertext(
                    {
                        'text_id': saved_it.source_text_id,
                        'author': saved_it.source_author,
                        'work': saved_it.source_work,
                        'reference': saved_it.source_reference,
                        'snippet': saved_it.source_snippet,
                        'language': saved_it.source_language,
                    },
                    {
                        'text_id': saved_it.target_text_id,
                        'author': saved_it.target_author,
                        'work': saved_it.target_work,
                        'reference': saved_it.target_reference,
                        'snippet': saved_it.target_snippet,
                        'language': saved_it.target_language,
                    },
                    {
                        'matched_lemmas': _parse_json_list(saved_it.matched_lemmas),
                        'matched_tokens': _parse_json_list(saved_it.matched_tokens),
                        'tesserae_score': saved_it.tesserae_score,
                        'intertext_score': saved_it.intertext_score,
                        'notes': saved_it.notes or '',
                        'tags': _parse_json_list(saved_it.tags),
                    },
                    current_user,
                )
                db.session.add(public_it)
                db.session.flush()
                saved_it.shared_to_public = True
                saved_it.public_intertext_id = public_it.id
            elif should_share and saved_it.shared_to_public and saved_it.public_intertext_id:
                public_it = Intertext.query.get(saved_it.public_intertext_id)
                if public_it:
                    _sync_public_intertext(public_it, saved_it, current_user)
            elif not should_share:
                _delete_public_copy(saved_it)
                saved_it.shared_to_public = False

        if saved_it.shared_to_public and saved_it.public_intertext_id:
            public_it = Intertext.query.get(saved_it.public_intertext_id)
            if public_it:
                _sync_public_intertext(public_it, saved_it, current_user)

        db.session.commit()
        return jsonify({'success': True, 'intertext': _serialize_saved_intertext(saved_it)})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to update saved intertext: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/my', methods=['POST'])
def save_personal_intertext():
    """Save an intertext to user's personal collection with scoring"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Login required to save intertexts'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        source = data.get('source', {})
        target = data.get('target', {})
        intertext_score = data.get('intertext_score', 0)
        
        if not source.get('text_id') or not target.get('text_id'):
            return jsonify({'error': 'Source and target text_id required'}), 400
        if not isinstance(intertext_score, int) or intertext_score < 1 or intertext_score > 5:
            return jsonify({'error': 'Valid intertext_score (1-5) required'}), 400

        share_to_public = bool(data.get('share_to_public', False))
        
        saved_it = SavedIntertext(
            user_id=current_user.id,
            source_text_id=source.get('text_id', ''),
            source_author=source.get('author', ''),
            source_work=source.get('work', ''),
            source_reference=source.get('reference', ''),
            source_snippet=source.get('snippet', ''),
            source_language=source.get('language', 'la'),
            target_text_id=target.get('text_id', ''),
            target_author=target.get('author', ''),
            target_work=target.get('work', ''),
            target_reference=target.get('reference', ''),
            target_snippet=target.get('snippet', ''),
            target_language=target.get('language', 'la'),
            matched_lemmas=json.dumps(data.get('matched_lemmas', [])),
            matched_tokens=json.dumps(data.get('matched_tokens', [])),
            tesserae_score=data.get('tesserae_score', 0.0),
            intertext_score=intertext_score,
            notes=data.get('notes', ''),
            tags=json.dumps(data.get('tags', [])),
            shared_to_public=share_to_public,
            created_at=datetime.now()
        )
        
        public_intertext_id = None
        if share_to_public:
            public_it = _build_public_intertext(source, target, data, current_user)
            db.session.add(public_it)
            db.session.flush()
            public_intertext_id = public_it.id
            saved_it.public_intertext_id = public_intertext_id
        
        db.session.add(saved_it)
        db.session.commit()
        
        logger.info(f"User {current_user.id} saved intertext {saved_it.id} (public: {share_to_public})")
        
        return jsonify({
            'success': True,
            'id': saved_it.id,
            'public_intertext_id': public_intertext_id,
            'message': 'Intertext saved to your collection' + (' and registered publicly' if share_to_public else '')
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to save personal intertext: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/my/<int:saved_id>/share', methods=['POST'])
def share_saved_intertext(saved_id):
    """Share a previously private saved intertext to the public repository"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Login required'}), 401
        
        saved_it = SavedIntertext.query.get(saved_id)
        if not saved_it:
            return jsonify({'error': 'Saved intertext not found'}), 404
        if saved_it.user_id != current_user.id:
            return jsonify({'error': 'Not authorized'}), 403
        if saved_it.shared_to_public:
            return jsonify({'error': 'Already shared publicly'}), 400
        
        public_it = _build_public_intertext(
            {
                'text_id': saved_it.source_text_id,
                'author': saved_it.source_author,
                'work': saved_it.source_work,
                'reference': saved_it.source_reference,
                'snippet': saved_it.source_snippet,
                'language': saved_it.source_language,
            },
            {
                'text_id': saved_it.target_text_id,
                'author': saved_it.target_author,
                'work': saved_it.target_work,
                'reference': saved_it.target_reference,
                'snippet': saved_it.target_snippet,
                'language': saved_it.target_language,
            },
            {
                'matched_lemmas': _parse_json_list(saved_it.matched_lemmas),
                'matched_tokens': _parse_json_list(saved_it.matched_tokens),
                'tesserae_score': saved_it.tesserae_score,
                'intertext_score': saved_it.intertext_score,
                'notes': saved_it.notes or '',
                'tags': _parse_json_list(saved_it.tags),
            },
            current_user,
        )
        db.session.add(public_it)
        db.session.flush()
        
        saved_it.shared_to_public = True
        saved_it.public_intertext_id = public_it.id
        db.session.commit()
        
        logger.info(f"User {current_user.id} shared saved intertext {saved_id} publicly as {public_it.id}")
        
        return jsonify({
            'success': True,
            'public_intertext_id': public_it.id,
            'message': 'Intertext registered in public repository'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to share intertext: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/my/<int:saved_id>', methods=['DELETE'])
def delete_saved_intertext(saved_id):
    """Delete a saved intertext from personal collection"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Login required'}), 401
        
        saved_it = SavedIntertext.query.get(saved_id)
        if not saved_it:
            return jsonify({'error': 'Saved intertext not found'}), 404
        if saved_it.user_id != current_user.id:
            return jsonify({'error': 'Not authorized'}), 403

        _delete_public_copy(saved_it)
        db.session.delete(saved_it)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to delete saved intertext: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/preferences', methods=['GET'])
def get_sharing_preference():
    """Get user's default sharing preference"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'share_to_public_default': True})
        return jsonify({'share_to_public_default': current_user.share_to_public_default})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/preferences', methods=['PUT'])
def update_sharing_preference():
    """Update user's default sharing preference"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Login required'}), 401
        
        data = request.get_json()
        if not data or 'share_to_public_default' not in data:
            return jsonify({'error': 'share_to_public_default required'}), 400
        
        current_user.share_to_public_default = bool(data['share_to_public_default'])
        db.session.commit()
        
        return jsonify({'success': True, 'share_to_public_default': current_user.share_to_public_default})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


_latin_lemma_table = None
_latin_lemma_to_forms = None

def _load_latin_lemmas():
    """Load Latin lemma lookup tables for morphological matching."""
    global _latin_lemma_table, _latin_lemma_to_forms
    if _latin_lemma_table is not None:
        return
    
    import os
    lemma_file = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'lemma_tables', 'latin_lemmas.json')
    if os.path.exists(lemma_file):
        try:
            with open(lemma_file, 'r') as f:
                _latin_lemma_table = json.load(f)
            _latin_lemma_to_forms = {}
            for form, lemma in _latin_lemma_table.items():
                if lemma not in _latin_lemma_to_forms:
                    _latin_lemma_to_forms[lemma] = set()
                _latin_lemma_to_forms[lemma].add(form)
            logger.info(f"Loaded {len(_latin_lemma_table)} Latin lemma entries")
        except Exception as e:
            logger.error(f"Failed to load Latin lemmas: {e}")
            _latin_lemma_table = {}
            _latin_lemma_to_forms = {}
    else:
        _latin_lemma_table = {}
        _latin_lemma_to_forms = {}


@intertext_bp.route('/expand-lemmas', methods=['POST'])
def expand_lemmas():
    """Expand a list of lemmas to all known word forms for highlighting.
    
    Takes a list of lemmas and returns all Latin word forms that share those lemmas.
    This enables proper highlighting of inflected forms (rege/regem, fato/fata, virum/virorum).
    """
    try:
        _load_latin_lemmas()
        
        data = request.get_json()
        if not data or 'lemmas' not in data:
            return jsonify({'error': 'lemmas array required'}), 400
        
        lemmas = data['lemmas']
        if not isinstance(lemmas, list):
            return jsonify({'error': 'lemmas must be an array'}), 400
        
        expanded_forms = set()
        
        for lemma in lemmas:
            if not lemma:
                continue
            lemma_lower = lemma.lower()
            lemma_normalized = lemma_lower.replace('v', 'u')
            
            expanded_forms.add(lemma_lower)
            expanded_forms.add(lemma_normalized)
            
            if _latin_lemma_to_forms:
                if lemma_normalized in _latin_lemma_to_forms:
                    expanded_forms.update(_latin_lemma_to_forms[lemma_normalized])
                if lemma_lower in _latin_lemma_to_forms:
                    expanded_forms.update(_latin_lemma_to_forms[lemma_lower])
                    
                base_lemma = _latin_lemma_table.get(lemma_normalized) or _latin_lemma_table.get(lemma_lower)
                if base_lemma and base_lemma in _latin_lemma_to_forms:
                    expanded_forms.update(_latin_lemma_to_forms[base_lemma])
        
        return jsonify({'forms': list(expanded_forms)})
    except Exception as e:
        logger.error(f"Failed to expand lemmas: {e}")
        return jsonify({'error': str(e)}), 500
