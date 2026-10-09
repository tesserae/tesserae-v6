"""
Downloads Blueprint - Provides downloadable resources for users and developers
"""
import os
import json
import zipfile
import tempfile
from io import BytesIO
from flask import Blueprint, send_file, jsonify, Response, after_this_request

from backend import restricted_texts

downloads_bp = Blueprint('downloads', __name__)

TEXTS_DIR = 'texts'
EMBEDDINGS_DIR = 'backend/embeddings'

RESTRICTED_NOTE = (
    'licensed for indexing and search only on the Tesserae site; not for redistribution')

def create_zip_from_directory(directory, prefix='', skip_files=None):
    """Create a zip file from a directory and return as BytesIO.

    `skip_files`, when given, is a set of filenames (not paths) at the top
    level of `directory` to leave out -- how a restricted text, which must
    stay on the server but never in a bundle anyone can walk off with, is
    withheld from a directory download without the caller needing to copy the
    directory first.
    """
    skip_files = skip_files or set()
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file in skip_files:
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, directory)
                if prefix:
                    arcname = os.path.join(prefix, arcname)
                zf.write(file_path, arcname)
        if skip_files:
            zf.writestr(
                os.path.join(prefix, 'README_RESTRICTED.txt') if prefix else 'README_RESTRICTED.txt',
                f'{len(skip_files)} text(s) withheld from this download: {RESTRICTED_NOTE}.\n')
    memory_file.seek(0)
    return memory_file

@downloads_bp.route('/downloads/texts/<language>')
def download_texts(language):
    """Download all texts for a language as a zip file"""
    if language not in ['la', 'grc', 'en', 'cop', 'he']:
        return jsonify({'error': 'Invalid language. Use: la, grc, en, cop, he'}), 400

    lang_dir = os.path.join(TEXTS_DIR, language)
    if not os.path.exists(lang_dir):
        return jsonify({'error': f'No texts found for {language}'}), 404

    try:
        skip = set(restricted_texts.filenames(language, texts_root=TEXTS_DIR))
        zip_buffer = create_zip_from_directory(lang_dir, f'texts_{language}', skip_files=skip)
        response = send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'tesserae_texts_{language}.zip'
        )
        if skip:
            response.headers['X-Tesserae-Restricted-Withheld'] = (
                f'{len(skip)} text(s) withheld: {RESTRICTED_NOTE}.')
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@downloads_bp.route('/downloads/embeddings/<language>')
def download_embeddings(language):
    """Download all embeddings for a language as a zip file.
    
    Streams to a temp file instead of building in memory,
    because embedding directories can be multiple GB.
    """
    if language not in ['la', 'grc']:
        return jsonify({'error': 'Invalid language. Use: la, grc'}), 400
    
    lang_dir = os.path.join(EMBEDDINGS_DIR, language)
    if not os.path.exists(lang_dir):
        return jsonify({'error': f'No embeddings found for {language}'}), 404
    
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        tmp_path = tmp.name
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zf:
            prefix = f'embeddings_{language}'
            for root, dirs, files in os.walk(lang_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, lang_dir)
                    arcname = os.path.join(prefix, arcname)
                    zf.write(file_path, arcname)
        
        @after_this_request
        def cleanup(response):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return response
        
        return send_file(
            tmp_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'tesserae_embeddings_{language}.zip'
        )
    except Exception as e:
        # Clean up temp file on error too
        try:
            os.unlink(tmp_path)
        except (OSError, UnboundLocalError):
            pass
        return jsonify({'error': str(e)}), 500

@downloads_bp.route('/downloads/dictionary')
def download_dictionary():
    """Download the Greek-Latin synonym dictionary"""
    try:
        from backend.synonym_dict import get_greek_latin_dict
        
        greek_latin_dict, _ = get_greek_latin_dict()
        
        # Convert set values to sorted lists for JSON serialization
        serializable_dict = {
            k: sorted(v) if isinstance(v, set) else v
            for k, v in greek_latin_dict.items()
        }
        
        dict_data = {
            'description': 'Greek-Latin vocabulary mappings for cross-lingual matching',
            'source': 'Tesserae V6',
            'format': 'Greek lemma -> List of Latin equivalents',
            'entries': len(serializable_dict),
            'dictionary': serializable_dict
        }
        
        json_str = json.dumps(dict_data, ensure_ascii=False, indent=2)
        return Response(
            json_str,
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=greek_latin_dictionary.json'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@downloads_bp.route('/downloads/compute-script')
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

@downloads_bp.route('/downloads/info')
def download_info():
    """Get information about available downloads"""
    info = {
        'texts': {},
        'embeddings': {}
    }
    
    for lang in ['la', 'grc', 'en', 'cop', 'he']:
        lang_dir = os.path.join(TEXTS_DIR, lang)
        if os.path.exists(lang_dir):
            files = [f for f in os.listdir(lang_dir) if f.endswith('.tess')]
            restricted = set(restricted_texts.filenames(lang, texts_root=TEXTS_DIR))
            entry = {
                'count': len(files) - len(restricted),
                'available': True
            }
            if restricted:
                entry['restricted_withheld'] = len(restricted)
                entry['restricted_note'] = RESTRICTED_NOTE
            info['texts'][lang] = entry
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
