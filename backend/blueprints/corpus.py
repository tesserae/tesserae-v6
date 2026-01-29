"""
Tesserae V6 - Corpus Blueprint
Routes for corpus and text management
"""
from flask import Blueprint, jsonify, request
import os
import re
import json
from pathlib import Path

from backend.logging_config import get_logger
from backend.utils import get_text_metadata, build_text_hierarchy
from backend.frequency_cache import get_corpus_frequencies, recalculate_language_frequencies

logger = get_logger('corpus')

PROVENANCE_FILE = Path(__file__).parent.parent / "text_provenance.json"
AUTHOR_DATES_FILE = Path(__file__).parent.parent / "author_dates.json"

_author_dates_cache = None

def get_author_dates():
    """Load and cache author dates."""
    global _author_dates_cache
    if _author_dates_cache is None:
        if AUTHOR_DATES_FILE.exists():
            with open(AUTHOR_DATES_FILE, 'r', encoding='utf-8') as f:
                _author_dates_cache = json.load(f)
        else:
            _author_dates_cache = {}
    return _author_dates_cache


def load_provenance():
    """Load text provenance data."""
    if PROVENANCE_FILE.exists():
        with open(PROVENANCE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"sources": {}, "texts": {}}

corpus_bp = Blueprint('corpus', __name__, url_prefix='/api')

_texts_dir = None
_text_processor = None
_get_processed_units = None


def natural_sort_key(s):
    """Sort strings with embedded numbers in natural order"""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(s))]


def init_corpus_blueprint(texts_dir, text_processor, get_processed_units_fn):
    """Initialize blueprint with required dependencies"""
    global _texts_dir, _text_processor, _get_processed_units
    _texts_dir = texts_dir
    _text_processor = text_processor
    _get_processed_units = get_processed_units_fn


@corpus_bp.route('/texts')
def get_texts():
    """Get all texts for a language"""
    language = request.args.get('language', 'la')
    lang_dir = os.path.join(_texts_dir, language)
    
    if not os.path.exists(lang_dir):
        return jsonify([])
    
    author_dates = get_author_dates().get(language, {})
    
    texts = []
    for filename in sorted(os.listdir(lang_dir)):
        if filename.endswith('.tess'):
            metadata = get_text_metadata(os.path.join(lang_dir, filename))
            metadata['language'] = language
            author_key = metadata.get('author_key', '').lower()
            if author_key in author_dates:
                metadata['year'] = author_dates[author_key].get('year')
                metadata['era'] = author_dates[author_key].get('era')
            else:
                metadata['year'] = None
                metadata['era'] = None
            texts.append(metadata)
    
    texts.sort(key=lambda x: (x['author'], x['title']))
    
    return jsonify(texts)


@corpus_bp.route('/authors')
def get_authors():
    """Get all authors with their works"""
    language = request.args.get('language', 'la')
    lang_dir = os.path.join(_texts_dir, language)
    
    if not os.path.exists(lang_dir):
        return jsonify([])
    
    author_dates = get_author_dates().get(language, {})
    
    authors = {}
    for filename in os.listdir(lang_dir):
        if filename.endswith('.tess'):
            metadata = get_text_metadata(os.path.join(lang_dir, filename))
            metadata['language'] = language
            author_key = metadata.get('author_key', '').lower()
            if author_key in author_dates:
                metadata['year'] = author_dates[author_key].get('year')
                metadata['era'] = author_dates[author_key].get('era')
            else:
                metadata['year'] = None
                metadata['era'] = None
            author = metadata['author']
            if author not in authors:
                authors[author] = {'works': [], 'year': metadata.get('year'), 'era': metadata.get('era')}
            authors[author]['works'].append(metadata)
    
    result = []
    for author in sorted(authors.keys()):
        result.append({
            'name': author,
            'year': authors[author].get('year'),
            'era': authors[author].get('era'),
            'works': sorted(authors[author]['works'], key=lambda x: natural_sort_key(x['title']))
        })
    
    return jsonify(result)


@corpus_bp.route('/corpus-status')
def get_corpus_status():
    """Get corpus expansion status and history."""
    import os
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    status_file = os.path.join(backend_dir, "corpus_status.json")
    if os.path.exists(status_file):
        with open(status_file, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({'error': 'Status file not found', 'path': status_file})


@corpus_bp.route('/provenance')
def get_provenance():
    """Get provenance information for texts."""
    text_id = request.args.get('text_id')
    
    provenance = load_provenance()
    
    if text_id:
        text_info = provenance.get('texts', {}).get(text_id)
        if text_info:
            source_key = text_info.get('source', '')
            source_info = provenance.get('sources', {}).get(source_key, {})
            return jsonify({
                'text': text_info,
                'source': source_info
            })
        return jsonify({'text': None, 'source': None})
    
    return jsonify({
        'sources': provenance.get('sources', {}),
        'texts': provenance.get('texts', {}),
        'total_tracked': len(provenance.get('texts', {}))
    })


@corpus_bp.route('/texts/hierarchy')
def get_texts_hierarchy():
    """Get hierarchical text structure: Author -> Work -> Parts"""
    language = request.args.get('language', 'la')
    lang_dir = os.path.join(_texts_dir, language)
    
    if not os.path.exists(lang_dir):
        return jsonify({'authors': []})
    
    author_dates = get_author_dates().get(language, {})
    
    texts = []
    for filename in os.listdir(lang_dir):
        if filename.endswith('.tess'):
            metadata = get_text_metadata(os.path.join(lang_dir, filename))
            author_key = metadata.get('author_key', '').lower()
            if author_key in author_dates:
                metadata['year'] = author_dates[author_key].get('year')
                metadata['era'] = author_dates[author_key].get('era')
            else:
                metadata['year'] = None
                metadata['era'] = None
            texts.append(metadata)
    
    hierarchy = build_text_hierarchy(texts)
    
    result = []
    for author_key in sorted(hierarchy.keys()):
        author_data = hierarchy[author_key]
        author_key_lower = author_key.lower()
        author_year = author_dates.get(author_key_lower, {}).get('year')
        author_era = author_dates.get(author_key_lower, {}).get('era')
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
            'year': author_year,
            'era': author_era,
            'works': works
        })
    
    return jsonify({'authors': result})


@corpus_bp.route('/text/<path:text_id>')
def get_text_content(text_id):
    """Get content of a specific text"""
    language = request.args.get('language', 'la')
    unit_type = request.args.get('unit_type', 'line')
    
    filepath = os.path.join(_texts_dir, language, text_id)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'Text not found'}), 404
    
    try:
        units = _get_processed_units(text_id, language, unit_type, _text_processor)
        metadata = get_text_metadata(filepath)
        
        return jsonify({
            'metadata': metadata,
            'units': units,
            'line_count': len(units)
        })
    except Exception as e:
        logger.error(f"Failed to get text content: {e}")
        return jsonify({'error': str(e)}), 500


@corpus_bp.route('/frequencies/<language>')
def get_frequencies(language):
    """Get corpus frequencies for a language"""
    freq_data = get_corpus_frequencies(language, _text_processor)
    
    if not freq_data:
        return jsonify({'error': 'No frequency data available'}), 404
    
    top_n = request.args.get('top', type=int, default=100)
    frequencies = freq_data.get('frequencies', {})
    
    sorted_freqs = sorted(frequencies.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    return jsonify({
        'language': language,
        'total_words': freq_data.get('total_words', 0),
        'unique_words': len(frequencies),
        'top_words': [{'word': w, 'count': c} for w, c in sorted_freqs]
    })


@corpus_bp.route('/frequencies/recalculate', methods=['POST'])
def recalculate_frequencies():
    """Recalculate corpus frequencies for a language"""
    data = request.get_json() or {}
    language = data.get('language', 'la')
    
    try:
        result = recalculate_language_frequencies(language, _text_processor)
        return jsonify({
            'success': True,
            'language': language,
            'total_words': result.get('total_words', 0) if result else 0
        })
    except Exception as e:
        logger.error(f"Failed to recalculate frequencies: {e}")
        return jsonify({'error': str(e)}), 500


@corpus_bp.route('/texts/preview', methods=['POST'])
def preview_text():
    """Preview text parsing before adding to corpus"""
    data = request.get_json() or {}
    content = data.get('content', '')
    language = data.get('language', 'la')
    author = data.get('author', '')
    work = data.get('work', '')
    
    if not content:
        return jsonify({'error': 'Content required'}), 400
    
    try:
        lines = content.strip().split('\n')
        preview_lines = []
        
        safe_author = ''.join(c if c.isalnum() or c in '._-' else '_' for c in author.lower()) if author else 'author'
        safe_work = ''.join(c if c.isalnum() or c in '._-' else '_' for c in work.lower()) if work else 'work'
        
        for i, line in enumerate(lines[:20], 1):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('<') and '>' in line:
                tag_end = line.index('>') + 1
                tag = line[:tag_end]
                text = line[tag_end:].strip()
            else:
                tag = f"<{safe_author}.{safe_work}.{i}>"
                text = line
            
            preview_lines.append({
                'line_num': i,
                'tag': tag,
                'text': text,
                'formatted': f"{tag} {text}"
            })
        
        return jsonify({
            'preview': preview_lines,
            'total_lines': len(lines),
            'suggested_filename': f"{safe_author}.{safe_work}.tess"
        })
    except Exception as e:
        logger.error(f"Failed to preview text: {e}")
        return jsonify({'error': str(e)}), 500


@corpus_bp.route('/texts/add', methods=['POST'])
def add_text():
    """Add a new text to the corpus (admin only)"""
    from backend.blueprints.admin import check_admin_auth
    
    if not check_admin_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    content = data.get('content', '')
    language = data.get('language', 'la')
    author = data.get('author', '')
    work = data.get('work', '')
    
    if not content or not author or not work:
        return jsonify({'error': 'Content, author, and work are required'}), 400
    
    try:
        safe_author = ''.join(c if c.isalnum() or c in '._-' else '_' for c in author.lower())
        safe_work = ''.join(c if c.isalnum() or c in '._-' else '_' for c in work.lower())
        filename = f"{safe_author}.{safe_work}.tess"
        
        lang_dir = os.path.join(_texts_dir, language)
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
        
        recalculate_language_frequencies(language, _text_processor)
        
        from backend.inverted_index import index_single_text
        index_result = index_single_text(filepath, language, _text_processor)
        
        # Clear search results cache for this language
        from backend.cache import clear_cache_for_language
        clear_cache_for_language(language)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'lines': len(formatted_lines),
            'indexed': index_result.get('status') == 'indexed' if index_result else False
        })
    except Exception as e:
        logger.error(f"Failed to add text: {e}")
        return jsonify({'error': str(e)}), 500
