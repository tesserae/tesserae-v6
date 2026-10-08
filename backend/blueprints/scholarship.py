"""Secondary scholarship for a passage: the Reader's Scholarship tab and the
connector's find_scholarship / get_commentary tools.

    GET /api/scholarship?work=&ref_start=&ref_end=[&work2=&ref2_start=&ref2_end=]
        articles, chapters and books from the open metadata services, ranked
        (band 1 cites both passages, 2 both works, 3 one passage), each with
        DOI and any legal open copy; plus the site's own commentaries at the
        span. The reader's library link is built client-side from a setting.
    GET /api/scholarship/commentary?work=&ref_start=&ref_end=
        the public-domain commentaries' notes at the span.
    POST /api/scholarship/translate  {text, commentator}
        a machine translation of one note by the local model, marked as such;
        cached, so a note is translated once.
"""
import hashlib
import json
import os
import time

import requests
from flask import Blueprint, jsonify, request

from backend import scholarship as S
from backend.usage import log_event
from backend.logging_config import get_logger

logger = get_logger('scholarship')
scholarship_bp = Blueprint('scholarship', __name__)

LLM_URL = os.environ.get('TESSERAE_LOCAL_LLM', 'http://127.0.0.1:8081/v1/chat/completions')
TRANSLATION_DISCLAIMER = 'Machine translation by a local model, unreviewed.'
LANGUAGE_NAMES = {'la': 'Latin', 'grc': 'Greek', 'he': 'Hebrew', 'ar': 'Arabic', 'fa': 'Persian',
                  'ur': 'Urdu', 'cop': 'Coptic', 'en': 'English', 'de': 'German', 'fr': 'French', 'it': 'Italian'}
_XLAT_DIR = os.path.join(S.CACHE_DIR, 'translations')


def _args():
    a = request.args
    return {k: (a.get(k) or '').strip() or None for k in ('work', 'ref_start', 'ref_end', 'work2', 'ref2_start', 'ref2_end', 'quote')}


@scholarship_bp.route('/scholarship')
def scholarship():
    p = _args()
    if not p['work'] or not p['ref_start']:
        return jsonify({'error': 'work and ref_start are required', 'results': []})
    try:
        limit = max(1, min(50, int(request.args.get('limit') or 20)))
    except ValueError:
        limit = 20
    out = S.find(p['work'], p['ref_start'], p['ref_end'], p['work2'], p['ref2_start'], p['ref2_end'], limit=limit, quote=p['quote'])
    out['commentary'] = S.commentary_at(p['work'], p['ref_start'], p['ref_end'])
    log_event('scholarship', work=p['work'], ref_start=p['ref_start'], ref_end=p['ref_end'],
              results_count=len(out.get('results') or []))
    if p['work2'] and p['ref2_start']:
        out['commentary2'] = S.commentary_at(p['work2'], p['ref2_start'], p['ref2_end'])
    return jsonify(out)


@scholarship_bp.route('/scholarship/commentary')
def commentary():
    p = _args()
    if not p['work'] or not p['ref_start']:
        return jsonify({'error': 'work and ref_start are required', 'commentary': []})
    return jsonify({'work': p['work'], 'ref_start': p['ref_start'], 'ref_end': p['ref_end'],
                    'commentary': S.commentary_at(p['work'], p['ref_start'], p['ref_end'])})


@scholarship_bp.route('/scholarship/sources')
def sources():
    """Every commentary held, grouped by commentator, with edition, source
    and licence, for the credits page: what the site shows must be credited
    where it came from."""
    return jsonify({'commentaries': S.commentary_sources()})


@scholarship_bp.route('/scholarship/translate', methods=['POST'])
def translate():
    d = request.get_json(silent=True) or {}
    text = (d.get('text') or '').strip()
    who = (d.get('commentator') or 'the commentator').strip()
    if not text:
        return jsonify({'error': 'text is required'})
    if len(text) > 4000:
        text = text[:4000]
    os.makedirs(_XLAT_DIR, exist_ok=True)
    key = hashlib.md5(text.encode('utf-8')).hexdigest()  # nosec B324
    path = os.path.join(_XLAT_DIR, key + '.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            return jsonify(json.load(fh))
    # One user message, instruction then text: the local model translates
    # reliably in that shape and echoed the Latin back when the instruction
    # sat in a system message (tried 2026-09-13; about 13 s for a long note).
    if len(text) > 1500:
        text = text[:1500]
    lang = LANGUAGE_NAMES.get((d.get('language') or '').strip().lower()) or 'original'
    label = 'Note' if lang == 'original' else lang
    prompt = (f'Translate the following {"" if lang == "original" else lang + " "}note by {who}, a commentator on '
              'the passage cited, into plain English. Output only the English translation, nothing else; do not '
              f'repeat the {lang}. Keep the word or phrase the note comments on in quotation marks at the start.'
              f'\n\n{label}:\n' + text + '\n\nEnglish:')
    try:
        r = requests.post(LLM_URL, json={'model': 'qwen3', 'temperature': 0, 'max_tokens': 500,
                                         'messages': [{'role': 'user', 'content': prompt}]}, timeout=180)
        r.raise_for_status()
        english = r.json()['choices'][0]['message']['content'].strip()
    except (requests.RequestException, KeyError, ValueError) as e:
        logger.warning('note translation failed: %s', e)
        return jsonify({'available': False, 'reason': 'The local translation model did not answer.'})
    out = {'available': True, 'text': english, 'disclaimer': TRANSLATION_DISCLAIMER, 'made': time.strftime('%Y-%m-%d')}
    try:
        tmp = f'{path}.{os.getpid()}.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass
    return jsonify(out)
