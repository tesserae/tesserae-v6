"""The text-lines route: /text/<id>/lines.

Moved out of backend/app.py unchanged (application-factory job, 2026-10-12).
"""

from flask import Blueprint, jsonify, request

from backend.utils import resolve_text_path
from backend.runtime import (
    TEXTS_DIR, api_route_for,
)

text_bp = Blueprint('text', __name__)
api_route = api_route_for(text_bp)

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
