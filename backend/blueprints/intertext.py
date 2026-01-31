"""
Intertext Repository Blueprint
Handles saving, browsing, and exporting registered intertexts.
"""
from flask import Blueprint, jsonify, request
from flask_login import current_user
from datetime import datetime
import json
import csv
import io

from backend.models import db, Intertext, SavedIntertext, User
from backend.logging_config import get_logger

logger = get_logger(__name__)

intertext_bp = Blueprint('intertext', __name__, url_prefix='/intertexts')


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
        
        intertexts = []
        for it in pagination.items:
            intertexts.append({
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
                'submitter_id': it.submitter_id,
                'submitter': {
                    'name': it.submitter_name or '',
                    'email': it.submitter_email or '',
                    'institution': it.submitter_institution or '',
                    'orcid': it.submitter_orcid or ''
                },
                'notes': it.notes,
                'tags': json.loads(it.tags) if it.tags else [],
                'status': it.status,
                'created_at': it.created_at.isoformat() if it.created_at else None
            })
        
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
        
        return jsonify({
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
            'submitter_id': it.submitter_id,
            'submitter': {
                'name': it.submitter_name or '',
                'email': it.submitter_email or '',
                'institution': it.submitter_institution or '',
                'orcid': it.submitter_orcid or ''
            },
            'notes': it.notes,
            'tags': json.loads(it.tags) if it.tags else [],
            'status': it.status,
            'created_at': it.created_at.isoformat() if it.created_at else None
        })
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
    """Flag an intertext for review - anyone can flag"""
    try:
        it = Intertext.query.get(intertext_id)
        if not it:
            return jsonify({'error': 'Intertext not found'}), 404
        
        data = request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify({'error': 'Invalid request body'}), 400
            
        if data.get('status') == 'flagged':
            it.status = 'flagged'
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Invalid status - only flagged is allowed'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to flag intertext: {e}")
        return jsonify({'error': str(e)}), 500


@intertext_bp.route('/<int:intertext_id>', methods=['DELETE'])
def delete_intertext(intertext_id):
    """Delete an intertext - requires authentication and ownership"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Login required to delete intertexts'}), 401
        
        it = Intertext.query.get(intertext_id)
        if not it:
            return jsonify({'error': 'Intertext not found'}), 404
        
        if it.submitter_id != current_user.id:
            return jsonify({'error': 'Only the submitter can delete this intertext'}), 403
        
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
        
        intertexts = []
        for it in pagination.items:
            intertexts.append({
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
                'intertext_score': it.intertext_score,
                'notes': it.notes,
                'tags': json.loads(it.tags) if it.tags else [],
                'shared_to_public': it.shared_to_public,
                'public_intertext_id': it.public_intertext_id,
                'created_at': it.created_at.isoformat() if it.created_at else None
            })
        
        return jsonify({
            'intertexts': intertexts,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        })
    except Exception as e:
        logger.error(f"Failed to list personal intertexts: {e}")
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
        intertext_score = data.get('intertext_score')
        
        if not source.get('text_id') or not target.get('text_id'):
            return jsonify({'error': 'Source and target text_id required'}), 400
        if intertext_score is None or intertext_score not in [1, 2, 3, 4, 5]:
            return jsonify({'error': 'Valid intertext_score (1-5) required'}), 400
        
        share_to_public = data.get('share_to_public', current_user.share_to_public_default)
        
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
            user_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email
            public_it = Intertext(
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
                user_score=intertext_score,
                submitter_id=current_user.id,
                submitter_name=user_name,
                submitter_email=current_user.email or '',
                submitter_institution=current_user.institution or '',
                submitter_orcid=current_user.orcid or '',
                notes=data.get('notes', ''),
                tags=json.dumps(data.get('tags', [])),
                status='pending',
                created_at=datetime.now()
            )
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
        
        user_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email
        public_it = Intertext(
            source_text_id=saved_it.source_text_id,
            source_author=saved_it.source_author,
            source_work=saved_it.source_work,
            source_reference=saved_it.source_reference,
            source_snippet=saved_it.source_snippet,
            source_language=saved_it.source_language,
            target_text_id=saved_it.target_text_id,
            target_author=saved_it.target_author,
            target_work=saved_it.target_work,
            target_reference=saved_it.target_reference,
            target_snippet=saved_it.target_snippet,
            target_language=saved_it.target_language,
            matched_lemmas=saved_it.matched_lemmas,
            matched_tokens=saved_it.matched_tokens,
            tesserae_score=saved_it.tesserae_score,
            user_score=saved_it.intertext_score,
            submitter_id=current_user.id,
            submitter_name=user_name,
            submitter_email=current_user.email or '',
            submitter_institution=current_user.institution or '',
            submitter_orcid=current_user.orcid or '',
            notes=saved_it.notes,
            tags=saved_it.tags,
            status='pending',
            created_at=datetime.now()
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
