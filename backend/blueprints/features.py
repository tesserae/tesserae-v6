"""Feature weights and toggles: /features/*.

Moved out of backend/app.py unchanged (application-factory job, 2026-10-12).
"""

from flask import Blueprint, jsonify, request

from backend.feature_extractor import feature_extractor
from backend.runtime import (
    ADMIN_PASSWORD, api_route_for,
)

features_bp = Blueprint('features', __name__)
api_route = api_route_for(features_bp)

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
