"""
Downloads Blueprint - Provides downloadable resources for users and developers
"""
import os
import json
import zipfile
import tempfile
from io import BytesIO
from flask import Blueprint, send_file, jsonify, Response

downloads_bp = Blueprint('downloads', __name__)

TEXTS_DIR = 'texts'
EMBEDDINGS_DIR = 'backend/embeddings'

def create_zip_from_directory(directory, prefix=''):
    """Create a zip file from a directory and return as BytesIO"""
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, directory)
                if prefix:
                    arcname = os.path.join(prefix, arcname)
                zf.write(file_path, arcname)
    memory_file.seek(0)
    return memory_file

@downloads_bp.route('/api/downloads/texts/<language>')
def download_texts(language):
    """Download all texts for a language as a zip file"""
    if language not in ['la', 'grc', 'en']:
        return jsonify({'error': 'Invalid language. Use: la, grc, en'}), 400
    
    lang_dir = os.path.join(TEXTS_DIR, language)
    if not os.path.exists(lang_dir):
        return jsonify({'error': f'No texts found for {language}'}), 404
    
    try:
        zip_buffer = create_zip_from_directory(lang_dir, f'texts_{language}')
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'tesserae_texts_{language}.zip'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@downloads_bp.route('/api/downloads/embeddings/<language>')
def download_embeddings(language):
    """Download all embeddings for a language as a zip file"""
    if language not in ['la', 'grc']:
        return jsonify({'error': 'Invalid language. Use: la, grc'}), 400
    
    lang_dir = os.path.join(EMBEDDINGS_DIR, language)
    if not os.path.exists(lang_dir):
        return jsonify({'error': f'No embeddings found for {language}'}), 404
    
    try:
        zip_buffer = create_zip_from_directory(lang_dir, f'embeddings_{language}')
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'tesserae_embeddings_{language}.zip'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@downloads_bp.route('/api/downloads/dictionary')
def download_dictionary():
    """Download the Greek-Latin synonym dictionary"""
    try:
        from backend.synonym_dict import get_greek_latin_dict
        
        greek_latin_dict = get_greek_latin_dict()
        
        dict_data = {
            'description': 'Greek-Latin vocabulary mappings for cross-lingual matching',
            'source': 'Tesserae V6',
            'format': 'Greek lemma -> List of Latin equivalents',
            'entries': len(greek_latin_dict),
            'dictionary': greek_latin_dict
        }
        
        json_str = json.dumps(dict_data, ensure_ascii=False, indent=2)
        return Response(
            json_str,
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=greek_latin_dictionary.json'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@downloads_bp.route('/api/downloads/compute-script')
def download_compute_script():
    """Download the embedding computation script"""
    script_content = '''#!/usr/bin/env python3
"""
Tesserae Embedding Computation Script
Generates SPhilBERTa embeddings for .tess text files

Requirements:
    pip install sentence-transformers numpy tqdm

Usage:
    python compute_embeddings.py --input texts/la --output embeddings/la
    python compute_embeddings.py --input texts/grc --output embeddings/grc
"""

import os
import sys
import argparse
import numpy as np
from pathlib import Path
from tqdm import tqdm

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("Please install: pip install sentence-transformers numpy tqdm")
    sys.exit(1)

def parse_tess_file(filepath):
    """Parse a .tess file and extract lines with references"""
    lines = []
    refs = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '\\t' in line:
                    parts = line.split('\\t', 1)
                    if len(parts) == 2:
                        refs.append(parts[0].strip())
                        lines.append(parts[1].strip())
                elif '<' in line and '>' in line:
                    ref_end = line.find('>')
                    refs.append(line[1:ref_end])
                    lines.append(line[ref_end+1:].strip())
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
    return lines, refs

def compute_embeddings_for_file(model, filepath, output_dir):
    """Compute and save embeddings for a single .tess file"""
    lines, refs = parse_tess_file(filepath)
    if not lines:
        return False
    
    filename = Path(filepath).stem
    embeddings = model.encode(lines, show_progress_bar=False)
    
    npy_path = os.path.join(output_dir, f"{filename}.npy")
    json_path = os.path.join(output_dir, f"{filename}.json")
    
    np.save(npy_path, embeddings)
    
    import json
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({'refs': refs, 'count': len(refs)}, f)
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Compute SPhilBERTa embeddings for Tesserae texts')
    parser.add_argument('--input', required=True, help='Input directory with .tess files')
    parser.add_argument('--output', required=True, help='Output directory for embeddings')
    parser.add_argument('--model', default='bowphs/SPhilBerta', help='Model name (default: bowphs/SPhilBerta)')
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Input directory not found: {args.input}")
        sys.exit(1)
    
    os.makedirs(args.output, exist_ok=True)
    
    print(f"Loading model: {args.model}")
    model = SentenceTransformer(args.model)
    
    tess_files = list(Path(args.input).glob('**/*.tess'))
    print(f"Found {len(tess_files)} .tess files")
    
    success = 0
    for filepath in tqdm(tess_files, desc="Computing embeddings"):
        if compute_embeddings_for_file(model, filepath, args.output):
            success += 1
    
    print(f"\\nCompleted: {success}/{len(tess_files)} files processed")
    print(f"Embeddings saved to: {args.output}")

if __name__ == '__main__':
    main()
'''
    return Response(
        script_content,
        mimetype='text/x-python',
        headers={'Content-Disposition': 'attachment; filename=compute_embeddings.py'}
    )

@downloads_bp.route('/api/downloads/info')
def download_info():
    """Get information about available downloads"""
    info = {
        'texts': {},
        'embeddings': {}
    }
    
    for lang in ['la', 'grc', 'en']:
        lang_dir = os.path.join(TEXTS_DIR, lang)
        if os.path.exists(lang_dir):
            files = [f for f in os.listdir(lang_dir) if f.endswith('.tess')]
            info['texts'][lang] = {
                'count': len(files),
                'available': True
            }
        else:
            info['texts'][lang] = {'count': 0, 'available': False}
    
    for lang in ['la', 'grc']:
        lang_dir = os.path.join(EMBEDDINGS_DIR, lang)
        if os.path.exists(lang_dir):
            files = [f for f in os.listdir(lang_dir) if f.endswith('.npy')]
            info['embeddings'][lang] = {
                'count': len(files),
                'available': True
            }
        else:
            info['embeddings'][lang] = {'count': 0, 'available': False}
    
    return jsonify(info)
