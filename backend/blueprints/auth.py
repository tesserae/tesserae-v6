"""Sign-in and account routes: /auth/*.

Moved out of backend/app.py unchanged (application-factory job, 2026-10-12).
"""
import os
import re

from flask import Blueprint, jsonify, request
from flask_login import current_user

from backend.models import db
from backend.marvin_auth import get_current_user_info, update_user_orcid, unlink_user_orcid
from backend.runtime import (
    api_route_for,
)

auth_bp = Blueprint('auth', __name__)
api_route = api_route_for(auth_bp)



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
